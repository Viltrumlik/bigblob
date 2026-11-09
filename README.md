<h1 align="center">bigblob</h1>

<p align="center">
  <b>Find what is making the git repository big.</b>
</p>

<p align="center">
  <a href="https://github.com/Viltrumlik/bigblob/actions/workflows/ci.yml"><img src="https://github.com/Viltrumlik/bigblob/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/dependencies-0-brightgreen" alt="Zero dependencies">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT"></a>
</p>

A fresh clone takes four minutes and the working tree is 30 MB. The weight is in history: a dump somebody committed once and deleted in the next commit is still in every clone, forever, and `du` will never show it to you.

```console
$ bigblob
   13.3 MB  ios/.build/ModuleCache/Swift-1811U2IA6GESV.swiftmodule   gone from HEAD
    9.4 MB  shots/demo.mp4                                           gone from HEAD
    6.2 MB  ios/.build/ModuleCache/Foundation-24LYWIP48SHNP.pcm      gone from HEAD

repository on disk: 177.2 MB
47.3 MB of the above is no longer in HEAD
it stays in every clone until the history is rewritten (git filter-repo)
```

`gone from HEAD` is the column that matters. Those files are not in your working tree at all — you cannot find them, delete them, or see them in `du`. They are pure weight, paid for by everyone who clones.

That example is real. Someone committed an Xcode build cache once, two years and many commits ago.

## Use

```bash
bigblob                # the 20 biggest objects in history
bigblob -n 50
bigblob --only-gone    # just the dead weight
bigblob --json
```

Exit codes: `0` ok · `1` not a git repository · `2` usage.

## Once you know

`bigblob` only reports. Rewriting history is destructive and belongs to you:

```bash
git filter-repo --path data/dump.sql --invert-paths
```

Everyone with a clone has to re-clone afterwards. Which is why it is worth knowing *before* the file has been in there for two years.

## It stays fast on big repositories

A repository can hold millions of objects, so sizes are streamed and only the top candidates are kept in memory rather than building a map of everything. A 177 MB repository answers in about one and a half seconds.

A blob that appears under several names — copied or moved — is reported under the name it carried most often, so one file is one row.

## Install

```bash
pipx install git+https://github.com/Viltrumlik/bigblob
```

Or take the file:

```bash
curl -O https://raw.githubusercontent.com/Viltrumlik/bigblob/main/bigblob.py
python3 bigblob.py
```

## Development

```bash
python3 -m unittest discover -s tests -v
```

13 tests. Each builds a real repository, commits a large file and deletes it, so the `gone from HEAD` logic is checked against real git output. CI runs on Ubuntu, macOS and Windows with Python 3.9 through 3.13.

## License

[MIT](LICENSE) © Alisher Muhammadaliyev ([@Viltrumlik](https://github.com/Viltrumlik))
