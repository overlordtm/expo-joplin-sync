import time
import requests
import json
import logging
import argparse
import os

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description="Process some data.")
parser.add_argument(
    "--dump",
    type=str,
    default="hosts.json",
    help="filename for dump (default: hosts.json)",
)
parser.add_argument(
    "--hosts",
    type=str,
    default="hosts.txt",
    help="filename for hosts (default: hosts.txt)",
)

api_url = os.getenv("JOPLIN_API_URL", "http://localhost:41184")
api_token = os.getenv(
    "JOPLIN_SYNC_TOKEN",
    "DUMMY",
)


class JoplinSync:
    def __init__(self, api_url, api_token):
        self.api_url = api_url
        self.api_token = api_token

    # Folders

    def folders(self):
        response = requests.get(f"{api_url}/folders?token={self.api_token}")
        response.raise_for_status()
        return response.json()["items"]

    def find_folder(self, search_query):
        response = requests.get(
            f"{api_url}/search?query={search_query}&type=folder&token={api_token}"
        )
        response.raise_for_status()
        return response.json()

    def get_folder(self, folder_id):
        response = requests.get(f"{api_url}/folders/{folder_id}?token={api_token}")
        response.raise_for_status()
        return response.json()

    def create_folder(self, folder_name, parent_folder_id=None):
        data = {"title": folder_name}
        if parent_folder_id:
            data["parent_id"] = parent_folder_id
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            f"{api_url}/folders?token={api_token}",
            data=json.dumps(data),
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    # Notes

    def find_note(self, search_query):
        response = requests.get(
            f"{api_url}/search?query={search_query}&type=note&token={api_token}"
        )
        response.raise_for_status()
        return response.json()

    def get_note(self, note_id):
        response = requests.get(f"{api_url}/notes/{note_id}?token={api_token}")
        response.raise_for_status()
        return response.json()

    def create_note(self, data):
        # return
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            f"{api_url}/notes?token={api_token}", data=json.dumps(data), headers=headers
        )
        response.raise_for_status()
        return response.json()

    def update_note(self, data):
        headers = {"Content-Type": "application/json"}
        response = requests.put(
            f"{api_url}/notes/{data['id']}?token={api_token}",
            data=json.dumps(data),
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


def read_hosts(pth="hosts.txt"):
    with open(pth, "r") as f:
        # read and trim lines
        return [line.strip() for line in f.readlines()]


def read_dump(pth="hosts.json"):
    with open(pth, "r") as f:
        return json.load(f)


def get_or_create_folder(
    j: JoplinSync, folder_name, folder_search, parent_folder_id=None
):
    folder = j.find_folder(folder_search)
    if len(folder["items"]) == 0:
        return j.create_folder(folder_name, parent_folder_id=parent_folder_id)
    elif len(folder["items"]) == 1:
        return folder["items"][0]
    else:
        raise Exception("More than one folder found")


def generate_service_check_tbl(d: dict):
    """Generates a markdown table for service checks"""

    tbl = []

    # table header
    fields = set(key for item in d["service_checks"] for key in item) - {
        "availability_status",
        "availability_check_output",
        "availability_change_time",
        "__typename",
        "special",
    }
    order = ["service_name", "ip", "protocol", "port", "source_network_id"]
    sorted_fields = [field for field in order if field in fields] + sorted(
        fields - set(order)
    )

    tbl.append(" | ".join(sorted_fields))
    tbl.append("|".join(["---"] * len(sorted_fields)))

    # table body
    service_checks = []
    for sc in d["service_checks"]:
        tbl.append(" | ".join([str(sc.get(col, "")) for col in sorted_fields]))

    return "\n".join(tbl)


def generate_summary(d: dict):
    lines = []

    keys = sorted(
        d.keys()
        - {
            "network_interfaces",
            "service_checks",
            "team_name",
            "__typename",
            "_id",
            "availability_change_time",
            "availability_status",
            "team",
            "team_unique_id",
            "has_services",
        }
    )

    def format_key(key):
        # convert snakecase to space separated words with capital letters
        return " ".join([word.capitalize() for word in key.split("_")])

    def format_value(val):
        if isinstance(val, list):
            return ", ".join(val)
        else:
            return val

    for key in keys:
        if d[key]:
            lines.append(f"{format_key(key)}\n: {format_value(d[key])}\n")

    return "\n".join(lines)


def generate_note(d: dict):
    raw_dump = json.dumps(d, indent=4)

    summary = generate_summary(d)
    service_checks_tbl = generate_service_check_tbl(d)

    body = f"""
# {d['expo_id']}

## Summary

{summary}

## Service checks

| {service_checks_tbl} |

## Raw expo dump

```json
{raw_dump}
```
"""
    # body = "test"

    tags = f"zone:{d['segment']},os:{d['os']}"

    return body, tags


def sync_note(j: JoplinSync, expo_data: dict, parent_id: str):
    """Syncs a single note to Joplin"""
    notebook_name = f"{expo_data['segment']}"
    note_title = f"{expo_data['expo_id']}"
    note_body, note_tags = generate_note(expo_data)

    logging.info(f"Syncing {note_title} to {notebook_name}")

    segment_folder = get_or_create_folder(j, notebook_name, notebook_name, parent_id)
    print("Segment folder", segment_folder)

    assert segment_folder["id"] is not None

    host_folder = get_or_create_folder(
        j, expo_data["expo_id"], expo_data["expo_id"], segment_folder["id"]
    )
    print("Host folder", host_folder)

    # list all fodlers, find child of current hoist_folder and find todos
    todo_folder = [
        folder
        for folder in j.folders()
        if folder["parent_id"] == host_folder["id"] and folder["title"] == "TODO"
    ]

    if len(todo_folder) == 0:
        todo_folder = j.create_folder("TODO", parent_folder_id=host_folder["id"])
    else:
        todo_folder = todo_folder[0]

    # create todos
    todos = [
        "/etc/passwd",
        "/etc/shadow",
        "/etc/group",
        "/etc/hosts",
        "/etc/sudoers*",
        "/etc/ssh",
        "/etc/login*",
        "/etc/default/*",
        "/etc/systemd*",
        "/etc/init.d/",
        "/etc/cron*",
        "/etc/profile*",
        "services: validate credentials",
        "services: check config",
        "services: check file perms",
        "services: check port bindings to public ips",
        "services: check service auth settings",
        "services: check for service accounts",
    ]

    for todo in todos:
        title = f"{todo}"
        notes = j.find_note(f"{title}")


        # find note that have todo_folder as parent
        notes2 = [note for note in notes["items"] if note["parent_id"] == todo_folder["id"]]
        assert len(notes2) <= 1

        note = notes2[0] if len(notes2) > 0 else {}

        print(json.dumps(note, indent=4))

        note["title"] = title
        note["body"] = expo_data["expo_id"]
        note["is_todo"] = True
        note["parent_id"] = todo_folder["id"]
        note["tags"] = "todo"

        if note.get("id"):
            logging.info(f"Updating TODO note {todo}")
            j.update_note(note)
        else:
            logging.info(f"Creating TODO note {todo}")
            j.create_note(note)

    # check if note exists
    assert host_folder["id"] is not None

    notes = j.find_note(f"{note_title} notebook:{notebook_name}")

    note = notes["items"].pop() if len(notes["items"]) > 0 else {}

    note["title"] = "00-Overview"
    note["body"] = note_body
    note["tags"] = note_tags
    note["parent_id"] = host_folder["id"]
    note["author"] = "joplin-expo-sync"

    if note.get("id"):
        logging.info(f"Updating note {note_title}")
        j.update_note(note)
    else:
        logging.info(f"Creating note {note_title}")
        j.create_note(note)


def sync(dump_path, host_path):
    """Syncs all hosts in the dump to Joplin"""
    my_hosts = read_hosts(host_path)
    expo_dump = read_dump(dump_path)

    j = JoplinSync(api_url, api_token)

    folder_hosts = get_or_create_folder(j, "10-Hosts", "10-Hosts")

    for host in expo_dump:
        if host["expo_id"] in my_hosts:
            try:
                sync_note(j, host, folder_hosts["id"])
                # time.sleep(0.1)
            except Exception as e:
                logging.exception(f"Error syncing {host['expo_id']}: {e}")


if __name__ == "__main__":
    args = parser.parse_args()

    logging.info(f"Dump file name: {args.dump}")
    logging.info(f"Hosts file name: {args.hosts}")
    sync(args.dump, args.hosts)
