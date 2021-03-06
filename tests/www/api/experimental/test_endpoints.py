# -*- coding: utf-8 -*-
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from datetime import timedelta
import json
import unittest
from six.moves.urllib.parse import quote_plus

from airflow.api.common.experimental.trigger_dag import trigger_dag
from airflow.models import DagBag, DagModel, DagRun, Pool, TaskInstance
from airflow.settings import Session
from airflow.utils.timezone import datetime, utcnow, parse as parse_datetime
from airflow.www import app as application
from tests.test_utils.db import clear_db_pools


class TestApiExperimental(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestApiExperimental, cls).setUpClass()
        session = Session()
        session.query(DagRun).delete()
        session.query(TaskInstance).delete()
        session.commit()
        session.close()

        dagbag = DagBag(include_examples=True)
        for dag in dagbag.dags.values():
            dag.sync_to_db()

    def setUp(self):
        super(TestApiExperimental, self).setUp()
        app = application.create_app(testing=True)
        self.app = app.test_client()

    def tearDown(self):
        session = Session()
        session.query(DagRun).delete()
        session.query(TaskInstance).delete()
        session.commit()
        session.close()
        super(TestApiExperimental, self).tearDown()

    def test_task_info(self):
        url_template = '/api/experimental/dags/{}/tasks/{}'

        response = self.app.get(
            url_template.format('example_bash_operator', 'runme_0')
        )
        self.assertIn('"email"', response.data.decode('utf-8'))
        self.assertNotIn('error', response.data.decode('utf-8'))
        self.assertEqual(200, response.status_code)

        response = self.app.get(
            url_template.format('example_bash_operator', 'DNE')
        )
        self.assertIn('error', response.data.decode('utf-8'))
        self.assertEqual(404, response.status_code)

        response = self.app.get(
            url_template.format('DNE', 'DNE')
        )
        self.assertIn('error', response.data.decode('utf-8'))
        self.assertEqual(404, response.status_code)

    def test_get_dag_code(self):
        url_template = '/api/experimental/dags/{}/code'

        response = self.app.get(
            url_template.format('example_bash_operator')
        )
        self.assertIn('BashOperator(', response.data.decode('utf-8'))
        self.assertEqual(200, response.status_code)

        response = self.app.get(
            url_template.format('xyz')
        )
        self.assertEqual(404, response.status_code)

    def test_task_paused(self):
        url_template = '/api/experimental/dags/{}/paused/{}'

        response = self.app.get(
            url_template.format('example_bash_operator', 'true')
        )
        self.assertIn('ok', response.data.decode('utf-8'))
        self.assertEqual(200, response.status_code)

        url_template = '/api/experimental/dags/{}/paused/{}'

        response = self.app.get(
            url_template.format('example_bash_operator', 'false')
        )
        self.assertIn('ok', response.data.decode('utf-8'))
        self.assertEqual(200, response.status_code)

    def test_trigger_dag(self):
        url_template = '/api/experimental/dags/{}/dag_runs'
        run_id = 'my_run' + utcnow().isoformat()
        response = self.app.post(
            url_template.format('example_bash_operator'),
            data=json.dumps({'run_id': run_id}),
            content_type="application/json"
        )

        self.assertEqual(200, response.status_code)
        response_execution_date = parse_datetime(json.loads(response.data.decode('utf-8'))['execution_date'])
        self.assertEqual(0, response_execution_date.microsecond)

        # Check execution_date is correct
        response = json.loads(response.data.decode('utf-8'))
        dagbag = DagBag()
        dag = dagbag.get_dag('example_bash_operator')
        dag_run = dag.get_dagrun(response_execution_date)
        self.assertEqual(run_id, dag_run.run_id)

        # Test error for nonexistent dag
        response = self.app.post(
            url_template.format('does_not_exist_dag'),
            data=json.dumps({}),
            content_type="application/json"
        )
        self.assertEqual(404, response.status_code)

    def test_delete_dag(self):
        url_template = '/api/experimental/dags/{}'

        from airflow import settings
        session = settings.Session()
        key = "my_dag_id"
        session.add(DagModel(dag_id=key))
        session.commit()
        response = self.app.delete(
            url_template.format(key),
            content_type="application/json"
        )
        self.assertEqual(200, response.status_code)

        response = self.app.delete(
            url_template.format('does_not_exist_dag'),
            content_type="application/json"
        )
        self.assertEqual(404, response.status_code)

    def test_trigger_dag_for_date(self):
        url_template = '/api/experimental/dags/{}/dag_runs'
        dag_id = 'example_bash_operator'
        execution_date = utcnow() + timedelta(hours=1)
        datetime_string = execution_date.isoformat()

        # Test correct execution with execution date
        response = self.app.post(
            url_template.format(dag_id),
            data=json.dumps({'execution_date': datetime_string}),
            content_type="application/json"
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(datetime_string, json.loads(response.data.decode('utf-8'))['execution_date'])

        dagbag = DagBag()
        dag = dagbag.get_dag(dag_id)
        dag_run = dag.get_dagrun(execution_date)
        self.assertTrue(dag_run,
                        'Dag Run not found for execution date {}'
                        .format(execution_date))

        # Test correct execution with execution date and microseconds replaced
        response = self.app.post(
            url_template.format(dag_id),
            data=json.dumps({'execution_date': datetime_string, 'replace_microseconds': 'true'}),
            content_type="application/json"
        )
        self.assertEqual(200, response.status_code)
        response_execution_date = parse_datetime(json.loads(response.data.decode('utf-8'))['execution_date'])
        self.assertEqual(0, response_execution_date.microsecond)

        dagbag = DagBag()
        dag = dagbag.get_dag(dag_id)
        dag_run = dag.get_dagrun(response_execution_date)
        self.assertTrue(dag_run,
                        'Dag Run not found for execution date {}'
                        .format(execution_date))

        # Test error for nonexistent dag
        response = self.app.post(
            url_template.format('does_not_exist_dag'),
            data=json.dumps({'execution_date': datetime_string}),
            content_type="application/json"
        )
        self.assertEqual(404, response.status_code)

        # Test error for bad datetime format
        response = self.app.post(
            url_template.format(dag_id),
            data=json.dumps({'execution_date': 'not_a_datetime'}),
            content_type="application/json"
        )
        self.assertEqual(400, response.status_code)

    def test_task_instance_info(self):
        url_template = '/api/experimental/dags/{}/dag_runs/{}/tasks/{}'
        dag_id = 'example_bash_operator'
        task_id = 'also_run_this'
        execution_date = utcnow().replace(microsecond=0)
        datetime_string = quote_plus(execution_date.isoformat())
        wrong_datetime_string = quote_plus(
            datetime(1990, 1, 1, 1, 1, 1).isoformat()
        )

        # Create DagRun
        trigger_dag(dag_id=dag_id,
                    run_id='test_task_instance_info_run',
                    execution_date=execution_date)

        # Test Correct execution
        response = self.app.get(
            url_template.format(dag_id, datetime_string, task_id)
        )
        self.assertEqual(200, response.status_code)
        self.assertIn('state', response.data.decode('utf-8'))
        self.assertNotIn('error', response.data.decode('utf-8'))

        # Test error for nonexistent dag
        response = self.app.get(
            url_template.format('does_not_exist_dag', datetime_string,
                                task_id),
        )
        self.assertEqual(404, response.status_code)
        self.assertIn('error', response.data.decode('utf-8'))

        # Test error for nonexistent task
        response = self.app.get(
            url_template.format(dag_id, datetime_string, 'does_not_exist_task')
        )
        self.assertEqual(404, response.status_code)
        self.assertIn('error', response.data.decode('utf-8'))

        # Test error for nonexistent dag run (wrong execution_date)
        response = self.app.get(
            url_template.format(dag_id, wrong_datetime_string, task_id)
        )
        self.assertEqual(404, response.status_code)
        self.assertIn('error', response.data.decode('utf-8'))

        # Test error for bad datetime format
        response = self.app.get(
            url_template.format(dag_id, 'not_a_datetime', task_id)
        )
        self.assertEqual(400, response.status_code)
        self.assertIn('error', response.data.decode('utf-8'))

    def test_dagrun_status(self):
        url_template = '/api/experimental/dags/{}/dag_runs/{}'
        dag_id = 'example_bash_operator'
        execution_date = utcnow().replace(microsecond=0)
        datetime_string = quote_plus(execution_date.isoformat())
        wrong_datetime_string = quote_plus(
            datetime(1990, 1, 1, 1, 1, 1).isoformat()
        )

        # Create DagRun
        trigger_dag(dag_id=dag_id,
                    run_id='test_task_instance_info_run',
                    execution_date=execution_date)

        # Test Correct execution
        response = self.app.get(
            url_template.format(dag_id, datetime_string)
        )
        self.assertEqual(200, response.status_code)
        self.assertIn('state', response.data.decode('utf-8'))
        self.assertNotIn('error', response.data.decode('utf-8'))

        # Test error for nonexistent dag
        response = self.app.get(
            url_template.format('does_not_exist_dag', datetime_string),
        )
        self.assertEqual(404, response.status_code)
        self.assertIn('error', response.data.decode('utf-8'))

        # Test error for nonexistent dag run (wrong execution_date)
        response = self.app.get(
            url_template.format(dag_id, wrong_datetime_string)
        )
        self.assertEqual(404, response.status_code)
        self.assertIn('error', response.data.decode('utf-8'))

        # Test error for bad datetime format
        response = self.app.get(
            url_template.format(dag_id, 'not_a_datetime')
        )
        self.assertEqual(400, response.status_code)
        self.assertIn('error', response.data.decode('utf-8'))


class TestPoolApiExperimental(unittest.TestCase):

    USER_POOL_COUNT = 2
    TOTAL_POOL_COUNT = USER_POOL_COUNT + 1  # including default_pool

    @classmethod
    def setUpClass(cls):
        super(TestPoolApiExperimental, cls).setUpClass()

    def setUp(self):
        super(TestPoolApiExperimental, self).setUp()
        app = application.create_app(testing=True)
        self.app = app.test_client()
        self.session = Session()

        clear_db_pools()
        self.pools = [Pool.get_default_pool()]
        for i in range(self.USER_POOL_COUNT):
            name = 'experimental_%s' % (i + 1)
            pool = Pool(
                pool=name,
                slots=i,
                description=name,
            )
            self.session.add(pool)
            self.pools.append(pool)
        self.session.commit()
        self.pool = self.pools[-1]

    def tearDown(self):
        super(TestPoolApiExperimental, self).tearDown()

    def _get_pool_count(self):
        response = self.app.get('/api/experimental/pools')
        self.assertEqual(response.status_code, 200)
        return len(json.loads(response.data.decode('utf-8')))

    def test_get_pool(self):
        response = self.app.get(
            '/api/experimental/pools/{}'.format(self.pool.pool),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data.decode('utf-8')),
                         self.pool.to_json())

    def test_get_pool_non_existing(self):
        response = self.app.get('/api/experimental/pools/foo')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data.decode('utf-8'))['error'],
                         "Pool 'foo' doesn't exist")

    def test_get_pools(self):
        response = self.app.get('/api/experimental/pools')
        self.assertEqual(response.status_code, 200)
        pools = json.loads(response.data.decode('utf-8'))
        self.assertEqual(len(pools), self.TOTAL_POOL_COUNT)
        for i, pool in enumerate(sorted(pools, key=lambda p: p['pool'])):
            self.assertDictEqual(pool, self.pools[i].to_json())

    def test_create_pool(self):
        response = self.app.post(
            '/api/experimental/pools',
            data=json.dumps({
                'name': 'foo',
                'slots': 1,
                'description': '',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        pool = json.loads(response.data.decode('utf-8'))
        self.assertEqual(pool['pool'], 'foo')
        self.assertEqual(pool['slots'], 1)
        self.assertEqual(pool['description'], '')
        self.assertEqual(self._get_pool_count(), self.TOTAL_POOL_COUNT + 1)

    def test_create_pool_with_bad_name(self):
        for name in ('', '    '):
            response = self.app.post(
                '/api/experimental/pools',
                data=json.dumps({
                    'name': name,
                    'slots': 1,
                    'description': '',
                }),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                json.loads(response.data.decode('utf-8'))['error'],
                "Pool name shouldn't be empty",
            )
        self.assertEqual(self._get_pool_count(), self.TOTAL_POOL_COUNT)

    def test_delete_pool(self):
        response = self.app.delete(
            '/api/experimental/pools/{}'.format(self.pool.pool),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data.decode('utf-8')),
                         self.pool.to_json())
        self.assertEqual(self._get_pool_count(), self.TOTAL_POOL_COUNT - 1)

    def test_delete_pool_non_existing(self):
        response = self.app.delete(
            '/api/experimental/pools/foo',
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data.decode('utf-8'))['error'],
                         "Pool 'foo' doesn't exist")

    def test_delete_default_pool(self):
        clear_db_pools()
        response = self.app.delete(
            '/api/experimental/pools/default_pool',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data.decode('utf-8'))['error'],
                         "default_pool cannot be deleted")


if __name__ == '__main__':
    unittest.main()
