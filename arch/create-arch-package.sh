#!/bin/bash
PROGVERSION=$(grep ^VERSION ../watchteleboy | cut -d '=' -f2)
PROGNAME=watchteleboy
ARCHIVENAME=${PROGNAME}-${PROGVERSION}.tar.gz

# create archive
tar czf $ARCHIVENAME -C ../ \
  DOCS \
  LICENSE \
  README \
  tvbrowser \
  ${PROGNAME}

# update version in PKGBUILD
sed -i -e "s/^pkgver=.*$/pkgver=${PROGVERSION}/" PKGBUILD
sed -i -e "s/^md5sums=('.*')$/md5sums=('$(md5sum ${ARCHIVENAME} | cut -f 1 -d " ")')/" PKGBUILD
exit 0
