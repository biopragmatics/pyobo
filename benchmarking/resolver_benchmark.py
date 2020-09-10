"""
The purpose of this python file is to benchmark how many queries per second the resolver
can handle. Since one of our previous bottlenecks was 5 per second from PubChem, any
improvement is nice!
"""

import time

import click
import requests
from requests_toolbelt.threaded import pool
from tqdm import tqdm

import pyobo


def _get_urls(prefix='doid', host='localhost', port=5000):
    identifiers = pyobo.get_id_name_mapping(prefix)
    return [
        f'http://{host}:{port}/resolve/{prefix}:{identifier}'
        for identifier in identifiers
    ]


def benchmark_sync(prefix='doid', host='localhost', port=5000):
    urls = _get_urls(prefix=prefix, host=host, port=port)

    start = time.time()
    for url in tqdm(urls, desc=f'benchmarking {prefix}'):
        res = requests.get(url)
        res.raise_for_status()
    elapsed = time.time() - start
    avg_elapsed = len(urls) / elapsed
    print(f'Made {len(urls)} requests in {elapsed:.2f} seconds. Avg = {avg_elapsed:.2f} requests/s')


def benchmark_async(prefix='doid', host='localhost', port=5000):
    urls = _get_urls(prefix=prefix, host=host, port=port)

    p = pool.Pool.from_urls(urls)

    start = time.time()

    # The following code is a modified version of ``p.join_all()`` with tqdm
    for session_thread in tqdm(p._pool, desc=f'benchmarking async {prefix}'):
        session_thread.join()

    elapsed = time.time() - start
    avg_elapsed = len(urls) / elapsed
    print(f'Made {len(urls)} async requests in {elapsed:.2f} seconds. Avg = {avg_elapsed:.2f} requests/s')


@click.command()
@click.option('--prefix', default='doid')
@click.option('--host', default='localhost')
@click.option('--port', default='5000')
def main(prefix, host, port):
    benchmark_sync(prefix=prefix, host=host, port=port)
    benchmark_async(prefix=prefix, host=host, port=port)


if __name__ == '__main__':
    main()
