#!/bin/bash

xgettext -d base --no-location -o discover_overlay/locales/base.pot discover_overlay/*.py discover_overlay/glade/settings.glade
sed -i 's/charset=CHARSET/charset=UTF-8/g' discover_overlay/locales/base.pot
