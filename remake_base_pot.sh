#!/bin/bash

xgettext -d base --no-location -o discover_overlay/locales/base.pot discover_overlay/*.py discover_overlay/glade/settings.glade
sed -i 's/charset=CHARSET/charset=UTF-8/g' discover_overlay/locales/base.pot

# Update all .po files with new keys

for dir in `find discover_overlay/locales/ -mindepth 1 -maxdepth 1 -type d`; do
    touch "${dir}/LC_MESSAGES/default.po"
    msgmerge -N ${dir}/LC_MESSAGES/default.po discover_overlay/locales/base.pot > ${dir}/LC_MESSAGES/default.po.new
    mv ${dir}/LC_MESSAGES/default.po.new ${dir}/LC_MESSAGES/default.po
done
