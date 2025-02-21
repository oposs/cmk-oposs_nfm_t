# checkmk NFM-T Monitor

This extension pack contains a checkmk special for monitoring a Nokia NFM-T for alarms.

## Development and Testing

if the files from the sample folder are present in /tmp, run

```
local/share/check_mk/agents/special/nfm_t -u user -p pass -v -d test
```

run `cmk -R` to load the plugin and `omd restart` to restart the entire cmk server

Enjoy!
Tobias Oetiker <tobi@oetiker.ch>
