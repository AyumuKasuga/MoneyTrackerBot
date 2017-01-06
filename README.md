MoneyTracker
============

I made this bot for my family to track our money spending, actually it's just interface for Google spread sheets.
Nothing interesting here.


Setup
=====

But if you really want to use this bot for your needs you should:

* [Get google credentials](http://gspread.readthedocs.io/en/latest/oauth2.html) and place this json to `conf/MoneyTracker.json`. 
* Fill `conf/config.json`
* Run docker container with command like this: `docker run --restart=always --name mt -d -v /home/ubuntu/money_tracker_conf/:/MoneyTracker/conf/ ayumukasuga/moneytrackerbot`
`/home/ubuntu/money_tracker_conf/` - folder with your configs
In this case you will use my docker image, but of course you can build your own.
* Say Hello to your new bot :). Bot will answer you only if you exist in `users` section.