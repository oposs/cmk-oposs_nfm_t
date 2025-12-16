# Checkmk NFM-T Monitor

This extension pack contains a Checkmk special agent for monitoring Nokia NFM-T managed nodes via the REST API. It discovers nodes and monitors their alarm status, with piggyback support for creating virtual hosts per node.

## Features

- REST API integration with Nokia NFM-T
- Automatic node discovery
- **Piggyback support**: Each NFM-T node becomes a virtual host in Checkmk
- Alarm monitoring with severity levels (critical, major, minor, warning, ok)
- **Service monitoring**: Connection/path services mapped to endpoint nodes
- System alarms (MNC-FM) displayed on the NFM-T host
- Connection retry logic and comprehensive error handling
- Historical metric data preservation via translations
- Full Checkmk 2.4+ compatibility

## Requirements

- Checkmk 2.4.0 or later
- Nokia NFM-T with REST API access
- Valid NFM-T API credentials

## Installation

1. Build the MKP package:
   ```bash
   mkp-builder build
   ```

2. Install via Checkmk GUI:
   - Setup → Extension Packages → Upload package

3. Or install via command line:
   ```bash
   mkp install oposs_nfm_t-*.mkp
   ```

## Configuration

1. Navigate to: Setup → Agents → Other integrations → NFM-T Monitor
2. Configure:
   - Username: NFM-T API username
   - Password: NFM-T API password (stored securely)
   - Port: TCP port (default: 443)
3. Apply the rule to your NFM-T host
4. Run service discovery on the host
5. The plugin will create piggyback hosts for each NFM-T node automatically

## Architecture

### Services on NFM-T Host

| Service | Description |
|---------|-------------|
| `NFM-T AGENT STATUS` | Agent health and monitored node count |
| `NFM-T System Alarms` | Alarms not assigned to any node (e.g., MNC-FM) |

### Services on Piggyback Hosts (per node)

| Service | Description |
|---------|-------------|
| `NFM-T Fault Manager Alarms` | Node-specific alarms with severity |
| `NFM-T Service {id}` | Connection/path services where this node is an endpoint |

### Service Monitoring

Services from `/oms1350/data/otn/connection/path` are monitored on both endpoint nodes:
- Service name: `NFM-T Service {id}` (stable identifier)
- Service details include: guiLabel, effectiveRate, port labels
- **Up state**: Monitored using `alarmSeverity` (Cleared=OK, Minor=WARN, Major/Critical=CRIT)
- **Not Up state**: Shown as UNKNOWN (gray)

### Data Sources

| API Endpoint | Data |
|--------------|------|
| `/oms1350/data/otn/node/` | Node list (piggyback hosts) |
| `/FaultManagement/rest/api/v2/alarms/details` | Alarms per node |
| `/oms1350/data/otn/connection/path` | Services/connections |

## Development and Testing

### Test Special Agent Directly

```bash
local/lib/python3/cmk_addons/plugins/oposs_nfm_t/libexec/agent_oposs_nfm_t \
    -u username -p 'password' --port 443 your-nfm-t-host
```

### Test Mode

If test data files are present in `/tmp`, you can run in test mode:

```bash
local/lib/python3/cmk_addons/plugins/oposs_nfm_t/libexec/agent_oposs_nfm_t \
    -u user -p pass -v -d test
```

Test files needed in `/tmp`:
- `nfm_t_alarms.json`
- `nfm_t_nodes.json`
- `nfm_t_services.json`

### Reload Plugin

After making changes:
```bash
cmk -R              # Reload configuration
omd restart         # Restart Checkmk site
```

### Service Discovery

```bash
cmk -II hostname --debug
```

### Test Checks

```bash
cmk -v --debug --checks=oposs_nfm_t hostname
```

## Plugin Structure

```
local/lib/python3/cmk_addons/plugins/oposs_nfm_t/
├── __init__.py                        # Package marker
├── libexec/
│   └── agent_oposs_nfm_t             # Special agent executable
├── server_side_calls/
│   └── oposs_nfm_t.py                # Command builder
├── rulesets/
│   └── oposs_nfm_t.py                # GUI configuration
├── agent_based/
│   └── oposs_nfm_t.py                # Check plugin
└── graphing/
    └── translations.py                # Metric translations
```

## Metrics

### Per Node (Piggyback Host)
- `oposs_nfm_t_alarm_count`: Total number of active alarms
- `oposs_nfm_t_error_count`: Number of critical/major alarms
- `oposs_nfm_t_warning_count`: Number of minor/warning alarms

### System Alarms (NFM-T Host)
- `oposs_nfm_t_system_alarm_count`: Total system alarms
- `oposs_nfm_t_system_error_count`: Critical/major system alarms
- `oposs_nfm_t_system_warning_count`: Minor/warning system alarms

## Migration from v0.3.0

Version 0.4.0 is a **breaking change** that requires Checkmk 2.4+. If upgrading from v0.3.0:

1. Historical metric data is automatically preserved via translations
2. Section name changed from `nfm_t` to `oposs_nfm_t` (handled automatically)
3. Reconfigure the ruleset (password migration is automatic)
4. Rediscover services on affected hosts

## License

GNU General Public License v2

## Author

Tobias Oetiker <tobi@oetiker.ch>

## Repository

https://github.com/oposs/cmk-oposs_nfm_t
