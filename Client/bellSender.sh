#!/bin/sh

# Set the DISPLAY environment variable
#export DISPLAY=:0
# Set the XAUTHORITY environment variable
#export XAUTHORITY=$HOME/.Xauthority

# get rid of the cursor so we don't see it when videos are running
#setterm -cursor off

# you can normally leave this alone
SERVICE="/home/pi/HBELL-Sender/bellSender.py"
sleep 10

echo "PID : $$"

if ps ax |grep bellSender.sh| grep -v $$ | grep -v grep > /dev/null
    then
    exit
fi

while true; do
        if ps ax | grep -v grep | grep $SERVICE > /dev/null
        then
        sleep 3;
else
        while true;
        do
            currenttime=$(date +%H)
            if  [ "$currenttime" -gt 23 ] || [ "$currenttime" -lt 02 ]
                then
                echo "$currenttime"
                exit
            fi
            python $SERVICE > /dev/null 2> /dev/null

        done

fi
done
