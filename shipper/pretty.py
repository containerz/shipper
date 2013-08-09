"""Pretty printing for containers and images
"""
from StringIO import StringIO
from contextlib import closing

from texttable import Texttable as TextTable

from .utils import time_ago, human_size

def images_to_ascii_table(images):
    """Just a method that formats the images to ascii table.
    Expects dictionary {host: [images]}
    and prints multiple tables
    """
    with closing(StringIO()) as out:
        for host, values in images.iteritems():
            out.write(str(host) + "\n")
            t = TextTable()
            t.set_deco(TextTable.HEADER)
            t.set_cols_dtype(['t'] *5)
            t.set_cols_align(["l"] *5)
            rows = []
            rows.append(['Repository', 'Tag', 'Id', 'Created', 'Size'])
            for image in values:
                rows.append([
                    image.repository or '<none>',
                    image.tag or '<none>',
                    image.id[:12],
                    time_ago(image.created),
                    human_size(image.size)
                    ])
            t.add_rows(rows)
            out.write(t.draw() + "\n\n")
        return out.getvalue()

def containers_to_ascii_table(containers):
    """Just a method that formats the images to ascii table.
    Expects dictionary {host: [images]}
    and prints multiple tables
    """
    with closing(StringIO()) as out:
        for host, values in containers.iteritems():
            out.write("[" + str(host) + "] \n")
            t = TextTable(max_width=400)
            t.set_deco(TextTable.HEADER)
            t.set_cols_dtype(['t'] * 6)
            t.set_cols_align(["l"] * 6)
            t.set_cols_width([12, 25, 25, 15, 20, 15])
            rows = []
            rows.append(
                ['Id', 'Image', 'Command', 'Created', 'Status', 'Ports'])
            for container in values:
                rows.append([
                        container.id[:12],
                        container.image,
                        container.command[:20],
                        time_ago(container.created),
                        container.status,
                        container.ports
                        ])
            t.add_rows(rows)
            out.write(t.draw() + "\n\n")
        return out.getvalue()
