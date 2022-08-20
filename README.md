# Markov-Bot-3

### config.json

Your directory must have a **config.json** file with the following fields:

**String fields**
The following fields must be strings: channel, username, oauth (starting with "oauth:", refresh, host, clientid, command_channel, blacklist_file

**List fields**

The following fields must be lists of strings: admins, ignored_users

**Integer fields**

The following fields must be integers: port, autosend, cooldown, reset, minlength, maxlength, maxchars

### blacklist.json

Your directory must have a **blacklist.json** file with the following fields (whose values are lists of strings): full_phrases, words, regex
