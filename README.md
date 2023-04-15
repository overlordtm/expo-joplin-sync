# joplin-sync

Script syncs some basic host info from EXPO dump to Joplin for your convinience. You can add own notes later.

## Quickstart

1. Install Joplin
2. Create new notebook
3. Enable API (Tools -> Options -> Web Clipper)
4. Copy token
5. Set env variable JOPLIN_SYNC_TOKEN
6. Dump hostnames of interest to file hosts.txt (one host per line, must match expo_id)
```
ansible -i inventories/linux_all.yml --list-hosts --limit 'bt_baf_int:&siem-*,bt_beg_dmz' all
```
7. Run script



## Usage

```
python joplin-sync/sync.py --help
usage: sync.py [-h] [--dump DUMP] [--hosts HOSTS]

Process some data.

options:
  -h, --help     show this help message and exit
  --dump DUMP    filename for dump (default: hosts.json)
  --hosts HOSTS  filename for hosts (default: hosts.txt)
```
