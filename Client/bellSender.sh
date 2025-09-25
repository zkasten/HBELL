#!/bin/sh

# Set the DISPLAY environment variable
#export DISPLAY=:0
# Set the XAUTHORITY environment variable
#export XAUTHORITY=$HOME/.Xauthority

# get rid of the cursor so we don't see it when videos are running
#setterm -cursor off

# you can normally leave this alone
SERVICE="/home/pi/bellSender.py"
sleep 10

echo "PID : $$"

if ps ax |grep pp.sh| grep -v $$ | grep -v grep > /dev/null
    then
    exit
fi

while true; do
        if ps ax | grep -v grep | grep $SERVICE > /dev/null
        then
        sleep 1;
else
        while true;
        do
            currenttime=$(date +%H)
            if  [ "$currenttime" -gt 23 ] || [ "$currenttime" -lt 02 ]
                then
                echo "$currenttime"
                exit
            fi
            python3 $SERVICE > /dev/null 2> /dev/null
            #python3 $SERVICE >> /tmp/pp.out 2>> /tmp/pp.err

        done

fi
done
