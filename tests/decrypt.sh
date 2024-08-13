# The test files in the repo are encrypted. Only those trusted by the maintainer will gain access to the decryption key
openssl enc -d -aes-256-cbc -pbkdf2 -in files.tar.gz | gunzip | tar -xvf -
