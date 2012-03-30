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

exit 0
