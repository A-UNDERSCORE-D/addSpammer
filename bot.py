import praw
import prawcore
import json
import os
import yaml
import time
from copy import copy

DEFAULT_CONFIG = {
    "client_id": "",
    "client_secret": "",
    "user_agent": "linux:cyborgupdatebot:0.1 (by /u/A_UNDEDRSCORE-D)",
    "username": "",
    "password": "",
    "last_run": 0,
    "baduser_flair": "",
    "config_sub": "",
    "config_post_id": "",
    "config_wiki_page": "",
    "config_comment": "#spamlist",
    "config_update_text": ""
}

config_filename = "config.json"


def loadconfig():
    if not os.path.exists(config_filename):
        with open(config_filename, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)

    with open(config_filename) as f:
        return json.load(f)

config = loadconfig()
assert config["password"], "This seems to be a firstrun. Please fill out config.json with the required data"
reddit = praw.Reddit(**config)
me = reddit.user

config_sub = reddit.subreddit(config["config_sub"])
config_thread = reddit.submission(id=config["config_post_id"])


sublist = [sub for sub in me.moderator_subreddits()]


def saveconfig():
    with open(config_filename, "w") as f:
        json.dump(config, f, indent=2)


def editpage(badusers: set):
    config_wiki = config_sub.wiki[config["config_wiki_page"]]
    lines = config_wiki.content_md.split("\r\n")
    linetoedit = -1
    for i, line in enumerate(lines):
        if line.startswith(config["config_comment"]):
            linetoedit = i + 1
            break
    assert linetoedit != -1
    line = lines[linetoedit]
    nicks = yaml.safe_load(line[13:])

    # this is to force uniqueness
    newnicks = copy(nicks)
    for user in badusers:
        if user not in nicks:
            newnicks.append(user)

    # make sure we only update things if we need to
    if nicks != newnicks:
        lines[linetoedit] = line[:13] + yaml.safe_dump(list(newnicks), default_style="'", default_flow_style=True)[:2]
        newpage_md = "\r\n".join(lines)
        config_wiki.edit(newpage_md, revision="Automated from flairBot")
        return True
    else:
        print("no changes made")
        return False


def checksub(subr) -> set:
    returnusers = set()
    for flairlog in subr.mod.log(action="editflair", limit=50, mod=reddit.user.me()):
        if flairlog.created_utc >= config["last_run"]:
            if flairlog.target_fullname and flairlog.target_fullname.startswith("t3_"):
                submission = reddit.submission(id=flairlog.target_fullname[3:])
                flair = submission.link_flair_text
                if flair == config["baduser_flair"]:
                    returnusers.add(flairlog.target_author)
                    submission.mod.remove(spam=True)

    return returnusers


def makepost():
    config_thread.reply(config["config_update_text"])


def run():

    if config["last_run"] == 0:
        config["last_run"] = time.time()
        saveconfig()
    rerun = set()
    while True:
        badusers = set()
        for sub in sublist:
            print("CHECKING:", sub)
            badusers.update(checksub(sub))
        if rerun:
            badusers.update(rerun)
        if badusers:
            print(badusers)
            try:
                if editpage(badusers):
                    config["last_run"] = time.time()
                    saveconfig()
                    print("Changes made. requesting reload.")
                    makepost()
                    rerun.clear()
            except prawcore.BadRequest:
                print("Caught 400 error. retrying on next run")
                rerun.update(badusers)

        else:
            print("no changes need to be made")
        time.sleep(60 * 5)


if __name__ == '__main__':
    run()
