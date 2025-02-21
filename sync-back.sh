#!/bin/sh
ssh cmk-volki-adm sudo -u kp -i tar zcf - $(find local -type f) | tar zxvf -