import re
import time

import gflags
from jinja2 import Template
from github3.client import RateLimitExceededError

from lp2gh import client
from lp2gh import exporter
from lp2gh import labels
from lp2gh import util

FLAGS = gflags.FLAGS
gflags.DEFINE_boolean('only_open_bugs', False,
                      'should we include closed bugs')

BUG_STATUS = ['New',
              'Incomplete',
              'Invalid',
              "Won't Fix",
              'Confirmed',
              'Triaged',
              'Opinion',
              'In Progress',
              'Fix Committed',
              'Fix Released']

BUG_CLOSED_STATUS = ['Invalid',
                     "Won't Fix",
                     'Fix Released']

BUG_IMPORTANCE = ['Critical',
                  'High',
                  'Medium',
                  'Low',
                  'Wishlist',
                  'Undecided']

MAX_RETRIES = 30


def limit_retry(e, repo, try_block, catch_block=None, give_up_block=None):
    retries = 0
    while True:
        try:
            return try_block()
        except RateLimitExceededError as err:
            if catch_block:
                catch_block(err)
            else:
                e.emit('exception: %s' % err.response.json())
            if retries >= MAX_RETRIES:
                if give_up_block:
                    give_up_block(err)
                break
            else:
                retries = retries + 1
                resp = repo.client.get("https://api.github.com/rate_limit")
                d = resp.json()
                limits = (d["resources"]["core"]["remaining"],
                          d["resources"]["core"]["reset"])
                e.emit('current rate limits: %s' % str(limits))
                if limits[0] > 0:
                    e.emit('sleeping quietly for %d minutes ...' % retries)
                    time.sleep(60 * retries)
                else:
                    offset = limits[1] - int(time.time()) + 10
                    e.emit(
                        'rate limit reached - have to sleep for %d seconds' % offset)
                    time.sleep(offset)


bug_matcher_re = re.compile(r'bug (\d+)')

BUG_SUMMARY_TEMPLATE = """
------------------------------------
Imported from Launchpad using lp2gh.

 * date created: {{date_created}}
 * owner: [{{owner}}](https://launchpad.net/~{{owner}})
 * assignee: [{{assignee}}](https://launchpad.net/~{{assignee}})
 {% if duplicate_of is not none -%}
 * duplicate of: #{{duplicate_of}}
 {% endif %}
 {% if duplicate is not none and duplicate|length > 0 -%}
 * the following issues have been marked as duplicates of this one:
   {% for dup in duplicates -%}
   * #{{ dup }}
   {% endfor %}
 {% endif %}
 * the launchpad [url]({{lp_url}})
"""


def message_to_dict(message):
    owner = message.owner
    return {'owner': owner.name,
            'content': message.content,
            'date_created': util.to_timestamp(message.date_created),
            }


def bug_task_to_dict(bug_task):
    bug = bug_task.bug
    assignee = bug_task.assignee
    owner = bug_task.owner
    messages = list(bug.messages)[1:]
    milestone = bug_task.milestone
    duplicates = bug.duplicates
    duplicate_of = bug.duplicate_of
    return {'id': bug.id,
            'status': bug_task.status,
            'importance': bug_task.importance,
            'assignee': assignee and assignee.name or None,
            'owner': owner.name,
            'milestone': milestone and milestone.name,
            'title': bug.title,
            'description': bug.description,
            'duplicate_of': duplicate_of and duplicate_of.id or None,
            'duplicates': [x.id for x in duplicates],
            'date_created': util.to_timestamp(bug_task.date_created),
            'comments': [message_to_dict(x) for x in messages],
            'tags': bug.tags,
            'security_related': bug.security_related,
            'lp_url': bug.web_link,
            }


def list_bugs(project, only_open=None):
    if only_open is None:
        only_open = FLAGS.only_open_bugs
    return project.searchTasks(status=only_open and None or BUG_STATUS, omit_duplicates=False)


def _replace_bugs(s, bug_mapping):
    matches = bug_matcher_re.findall(s)
    for match in matches:
        if match in bug_mapping:
            new_id = bug_mapping[match]
            s = s.replace(f'bug {match}', f'bug #{new_id}')
    return s


def translate_auto_links(bug, bug_mapping):
    """Update references to launchpad bug numbers to reference issues."""
    bug['description'] = _replace_bugs(bug['description'], bug_mapping)
    # bug['description'] = '```\n' + bug['description'] + '\n```'
    for comment in bug['comments']:
        comment['content'] = _replace_bugs(comment['content'], bug_mapping)
        # comment['content'] = '```\n' + comment['content'] + '\n```'

    return bug


def add_summary(bug, bug_mapping):
    """Add the summary information to the bug."""
    t = Template(BUG_SUMMARY_TEMPLATE)
    bug['duplicate_of'] = bug['duplicate_of'] in bug_mapping and bug_mapping[bug['duplicate_of']] or None
    bug['duplicates'] = [bug_mapping[x] for x in bug['duplicates']
                         if x in bug_mapping]
    bug['description'] = bug['description'] + '\n' + t.render(bug)
    return bug


def export(project, only_open=None):
    o = []
    c = client.Client()
    p = c.project(project)
    e = exporter.Exporter()
    bugs = list_bugs(p, only_open=only_open)
    for x in bugs:
        e.emit('fetching %s' % x.title)
        rv = bug_task_to_dict(x)
        o.append(rv)
    return o


def import_(repo, bugs, milestones_map=None):
    e = exporter.Exporter()
    labellist = repo.labels()
    create_bug_status_labels(labellist, e)
    create_bug_importance_labels(labellist, e)
    tags_map = create_tag_labels(labellist, bugs, e)

    mapping = create_issue_if_not_exists(bugs, repo, tags_map, e)
    add_issue_comments_and_summary(bugs, mapping, milestones_map, repo, e)

    return mapping


def add_issue_comments_and_summary(bugs, mapping, milestones_map, repo, e):
    for bug in bugs:
        e.emit('second pass on issue %s' % bug['title'])
        bug = translate_auto_links(bug, mapping)
        bug = add_summary(bug, mapping)
        issue_id = mapping[bug['id']]
        issue = repo.issue(issue_id)

        # add all the comments
        comments = repo.comments(issue_id)
        for msg in bug['comments']:
            # TODO(termie): username mapping
            by_line = f"(by [{msg['owner']}](https://launchpad.net/~{msg['owner']}))"
            limit_retry(e, repo, lambda: comments.append(
                body=f"{by_line}\n{msg['content']}"))

        # update the issue
        params = {'body': bug['description']}
        if bug['status'] in BUG_CLOSED_STATUS:
            params['state'] = 'closed'

        # NOTE(termie): workaround a bug in github where it does not allow
        #               creating bugs that are assigned to double-digit milestones
        #               but does allow editing an existing bug
        if bug['milestone']:
            params['milestone'] = milestones_map[bug['milestone']]
        limit_retry(e, repo, lambda: issue.update(params))


def create_issue_if_not_exists(bugs, repo, tags_map, e):
    mapping = {}
    # first pass
    issues = repo.issues()
    for bug in bugs:
        e.emit('create issue %s' % bug['title'])
        clean_mentions(bug)
        params = {'title': bug['title'],
                  'body': bug['description'],
                  'labels': bug['tags'] + [bug['importance']] + [bug['status']],
                  }

        # NOTE(termie): workaround for github case-sensitivity bug
        params['labels'] = list(set(
            [labels.translate_label(tags_map[x.lower()]) for x in params['labels']]))

        e.emit('with params: %s' % params)
        found_item = next(
            (issue for issue in issues.datalist if issue['title'] == bug['title']), None)
        if found_item is None:
            rv = limit_retry(e, repo, lambda: issues.append(**params))
            mapping[bug['id']] = rv['number']
        else:
            mapping[bug['id']] = found_item['number']
    return mapping


def clean_mentions(bug):
    bug['description'] = util.remove_mentions(bug['description'])
    bug['title'] = util.remove_mentions(bug['title'])
    for msg in bug['comments']:
        msg['content'] = util.remove_mentions(msg['content'])


def create_tag_labels(labellist, bugs, e):
    tags = []
    for x in bugs:
        tags.extend(x['tags'])
    tags = set(tags)

    # NOTE(termie): workaround for github case-sensitivity bug
    defaults_lower = [x.lower() for x in (BUG_STATUS + BUG_IMPORTANCE)]
    tags = [x for x in tags if str(x.lower()) not in defaults_lower]
    tags_map = dict((x.lower(), x)
                    for x in (tags + BUG_STATUS + BUG_IMPORTANCE))

    for tag in tags:
        try:
            e.emit('create label %s' % tag)
            labels.create_label(labellist, tag)
        except Exception as err:
            e.emit('exception: %s' % repr(err))
    return tags_map


def create_bug_importance_labels(labellist, e):
    for importance in BUG_IMPORTANCE:
        try:
            e.emit('create label %s' % importance)
            labels.create_label(labellist, importance, 'ffdddd')
        except Exception as err:
            e.emit('exception: %s' % repr(err))


def create_bug_status_labels(labellist, e):
    for status in BUG_STATUS:
        try:
            e.emit('create label %s' % status)
            labels.create_label(labellist, status, 'ddffdd')
        except Exception as err:
            e.emit('exception: %s' % repr(err))
    return e
