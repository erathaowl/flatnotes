# Tagging

Tags are hashtags written in a note's Markdown content, outside code blocks.

Example:

```markdown
# Holiday Ideas

- Amsterdam
- Geneva
- Zurich
- Rome

#personal #holiday
```

In this example, the note is tagged `personal` and `holiday`.

Valid tag characters are ASCII letters (`a-z`, `A-Z`), digits (`0-9`), underscore (`_`), and hyphen (`-`). Tags are case-insensitive, so `#work`, `#Work`, and `#WORK` refer to the same tag.

Examples:

- `#work`: find notes with the work tag.
- `tags:work`: equivalent field query.
- `tags:personal AND title:holiday`: combine a tag and a title.
- `NOT tags:*`: list notes without tags.

Tags appear in the existing private search index. Publishing an individual note does not expose its tags through an anonymous search API.

See [Advanced Searching](https://github.com/erathaowl/flatnotes/wiki/Advanced-Searching).
