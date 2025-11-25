#!/bin/bash
# DIR=$(dirname $0)
# if [ "$DIR" = "." ]; then
# DIR=$(pwd)
# fi
# iris-community login need no username and password

# echo " Merge configuration..." 
# iris merge iris /external/irismerge.conf /usr/irissys/iris.cpf

iris session $ISC_PACKAGE_INSTANCENAME -U USER <<- EOF
zn "USER"
do \$SYSTEM.OBJ.Load("/dur/TestNameSpace/src/cls/TestCode/Run.cls", "cuk")
exit
halt
EOF
echo ""
echo "Installation complete."
echo ""

echo "stop iris and purge unnecessary files..."
iris stop $ISC_PACKAGE_INSTANCENAME quietly
rm -rf $ISC_PACKAGE_INSTALLDIR/mgr/journal.log 
rm -rf $ISC_PACKAGE_INSTALLDIR/mgr/IRIS.WIJ
rm -rf $ISC_PACKAGE_INSTALLDIR/mgr/journal/*
# rm -rf /dur/*

exit 0
