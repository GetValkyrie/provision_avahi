#!/usr/bin/python

import os
import logging
import dbus
import gobject
import avahi
from encodings.idna import ToASCII
from dbus.mainloop.glib import DBusGMainLoop

aliases = [ u'foo.local', u'bar.local', u'quux.local' ]

domain = "" # Domain to publish on, default to .local
host = "" # Host to publish records for, default to localhost

group = None #our entry group
rename_count = 12 # Counter so we only rename after collisions a sensible number of times

class Settings:
    # Got these from /usr/include/avahi-common/defs.h
    TTL = 60
    CLASS_IN = 0x01
    TYPE_CNAME = 0x05

    ALIASES_CONFIG = "/etc/avahi/aliases"
    ALIAS_CONF_PATH = "/etc/avahi/aliases.d"
    #ALIAS_DEFINITIONS =[ os.path.join(ALIAS_CONF_PATH, config_file) for config_file in os.listdir(ALIAS_CONF_PATH) ]

class AvahiAliases:
    def __init__(self, *args, **kwargs):

        # setup logging
        pass
        #self.logger = logging.getLogger(os.path.basename(__file__))
        #self.logger.setLevel(logging.DEBUG)
        # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # self.logger.setFormatter(formatter)
        #handler = logging.handlers.SysLogHandler(address = '/dev/log')
        #self.logger.addHandler(handler)

    def get_aliases(self, path=None):
        """ Steps through all config alias files and builds a set of aliases """
        aliases = set()
        for config_file_path in path :
            config_file = open(config_file_path, 'r')
            for line in config_file :
                entry = line.strip('\n')
                if len(entry) > 0 and not entry.startswith("#"):
                    aliases.add(entry)
            config_file.close()

        return aliases

    def encode(self, name):
        """ convert the string to ascii
            copied from https://gist.github.com/gdamjan/3168336
        """
        return '.'.join( ToASCII(p) for p in name.split('.') if p )


    def encode_rdata(self, name):
        """
            copied from https://gist.github.com/gdamjan/3168336
        """
        def enc(part):
            a = ToASCII(part)
            return chr(len(a)), a
        return ''.join( '%s%s' % enc(p) for p in name.split('.') if p ) + '\0'

    def run(self, *args, **kwargs):
        """ runner for python-daemon """
        self.aliases = self.get_aliases(Settings.ALIAS_DEFINITIONS)
        #self.logger.info("Announcing aliases [{}]".format(" ".join(self.aliases)))

        for cname in self.aliases:
            cname = unicode(cname, locale.getpreferredencoding())
            print "Announcing", cname
            self.publish(cname)

        print "Announced all aliases"

        while True:
            time.sleep(Settings.TTL)
        self.logger.info("Stopping")
        sys.exit(0)


    def add_service(self):
        global group, serviceName, serviceType, servicePort, serviceTXT, domain, host
        if group is None:
            group = dbus.Interface(
                    bus.get_object( avahi.DBUS_NAME, server.EntryGroupNew()),
                    avahi.DBUS_INTERFACE_ENTRY_GROUP)
            group.connect_to_signal('StateChanged', self.entry_group_state_changed)

        for cname in aliases:
            print "Adding service '%s' of type '%s' ..." % (cname, 'CNAME')
            cname = self.encode(cname)
            rdata = self.encode_rdata(server.GetHostNameFqdn())
            rdata = avahi.string_to_byte_array(rdata)

            group.AddRecord(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, dbus.UInt32(0),
                cname, Settings.CLASS_IN, Settings.TYPE_CNAME, Settings.TTL, rdata)

        group.Commit()

    def remove_service(self):
        global group

        if not group is None:
            group.Reset()

    def server_state_changed(self, state):
        if state == avahi.SERVER_COLLISION:
            print "WARNING: Server name collision"
            self.remove_service()
        elif state == avahi.SERVER_RUNNING:
            self.add_service()

    def entry_group_state_changed(self, state, error):
        global serviceName, server, rename_count

        print "state change: %i" % state

        if state == avahi.ENTRY_GROUP_ESTABLISHED:
            print "Service established."
        elif state == avahi.ENTRY_GROUP_COLLISION:

            rename_count = rename_count - 1
            if rename_count > 0:
                name = server.GetAlternativeServiceName(name)
                print "WARNING: Service name collision, changing name to '%s' ..." % name
                self.remove_service()
                self.add_service()

            else:
                print "ERROR: No suitable service name found after %i retries, exiting." % n_rename
                main_loop.quit()
        elif state == avahi.ENTRY_GROUP_FAILURE:
            print "Error in group state changed", error
            main_loop.quit()
            return

if __name__ == '__main__':
    DBusGMainLoop( set_as_default=True )

    main_loop = gobject.MainLoop()
    bus = dbus.SystemBus()

    server = dbus.Interface(
            bus.get_object( avahi.DBUS_NAME, avahi.DBUS_PATH_SERVER ),
            avahi.DBUS_INTERFACE_SERVER )

    process = AvahiAliases()

    server.connect_to_signal( "StateChanged", process.server_state_changed )
    process.server_state_changed( server.GetState() )


    try:
        main_loop.run()
    except KeyboardInterrupt:
        pass

    if not group is None:
        group.Free()
