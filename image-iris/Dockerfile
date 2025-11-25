ARG IRIS_IMAGE=containers.intersystems.com/intersystems/irishealth-community
ARG IRIS_VERSION=2025.3
FROM $IRIS_IMAGE:$IRIS_VERSION
USER irisowner
WORKDIR /dur
# Adding source code that will be loaded by the installer
COPY --chown=irisowner:irisowner buildsource /dur

# iris setup 
RUN find . -name '.DS_Store' -type f -delete
RUN ISC_CPF_MERGE_FILE=/dur/merge/merge.cpf iris start $ISC_PACKAGE_INSTANCENAME &&\
    #iris merge $ISC_PACKAGE_INSTANCENAME /dur/merge/merge.cpf &&\
    /dur/loader.sh
    
