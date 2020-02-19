# charms.requirementstxt

A Python library, to aid the development of charms, that will automatically install Python dependencies as declared by a `requirements.txt` file in the root of the charm.

## Usage

Install the charms.requirementstxt library in your charm:

```bash
git submodule add https://github.com/AdamIsrael/charms.osm mod/charms.osm
mkdir -p lib/charms
ln -s ../mod/charms.osm/charms/osm lib/charms/osm
```

Import the `charms.requirementstxt` library early, before any dependencies it may install.

In `src/charm.py`:

```python
#!/usr/bin/env python3

import sys

sys.path.append("lib")

import charms.requirementstxt
...

```