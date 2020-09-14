#!/usr/bin/env python3

# Copyright 2017 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
from datetime import datetime

DUMP = 'dump.txt'

def print_dump(file):
    if os.path.exists(file):
        with open(file, "r") as fp:
            output = fp.read()
        os.remove(file)
        print(output)
    else:
        print(f'unable to find dump file: {file}')


def call(cmd, dump=False):
    started = datetime.now()

    redirect = ' > {DUMP}}' if dump else ''
    status = os.system(f'{cmd}{redirect}')

    ended = datetime.now()
    print(f'+{cmd} completed in {started-ended}')
    if status:
        if dump:
            print_dump(DUMP)
        raise OSError(f'invocation failed: {dump}')


def main():
    call('time python3 make_db.py --buckets buckets.yaml --junit --threads 32')

    bq_cmd = 'bq load --source_format=NEWLINE_DELIMITED_JSON --max_bad_records=1000'
    mj_cmd = 'pypy make_json.py'

    mj_ext = ''
    bq_ext = ''
    try:
        call(mj_cmd + ' --days 1 --assert-oldest 1.9')
    except OSError:
        # cycle daily/weekly tables
        bq_ext = ' --replace'
        mj_ext = ' --reset-emitted'

    call(mj_cmd + mj_ext + ' --days 1 | pv | gzip > build_day.json.gz')
    call(bq_cmd + bq_ext + ' k8s-gubernator:build.day build_day.json.gz schema.json', dump=True)

    call(mj_cmd + mj_ext + ' --days 7 | pv | gzip > build_week.json.gz')
    call(bq_cmd + bq_ext + ' k8s-gubernator:build.week build_week.json.gz schema.json', dump=True)

    call(mj_cmd + ' | pv | gzip > build_all.json.gz')
    call(bq_cmd + ' k8s-gubernator:build.all build_all.json.gz schema.json', dump=True)

    call('python3 stream.py --poll kubernetes-jenkins/gcs-changes/kettle '
         ' --dataset k8s-gubernator:build --tables all:0 day:1 week:7 --stop_at=1')


if __name__ == '__main__':
    os.chdir(os.path.dirname(__file__))
    os.environ['TZ'] = 'America/Los_Angeles'
    main()
