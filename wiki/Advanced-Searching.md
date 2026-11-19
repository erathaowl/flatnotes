# Advanced Searching

flatnotes uses Whoosh for full-text search over note titles, content, and tags. These searches are available after authentication in `password` and `totp` modes. The public link viewer does not provide anonymous global search.

## AND and OR searches

- `this that` searches for notes containing **both** terms (AND is the default).
- `this OR that` matches notes containing either term; `OR` must be uppercase.
- `"this that"` searches for an exact phrase.

## Wildcards

- `?` matches one character.
- `*` matches any number of characters.

## Search fields

Available fields:

- `title`: the note title.
- `content`: the Markdown content.
- `tags`: hashtags extracted from content.
- `last_modified`: file modification date.

Without a field prefix, the default search covers title, content, and tags. The field syntax uses a colon (`:`):

```text
title:holiday
content:"project plan"
tags:personal AND title:holiday
tags:work AND project
last_modified:today
last_modified:20220131
tags:work AND last_modified:[20220101 to 20220131]
```

Tag shortcuts are supported: `#work` matches `tags:work`. Use `*` to list all notes, or `NOT tags:*` to find untagged notes.

See [Tagging](https://github.com/erathaowl/flatnotes/wiki/Tagging) and [Home](https://github.com/erathaowl/flatnotes/wiki/Home).
