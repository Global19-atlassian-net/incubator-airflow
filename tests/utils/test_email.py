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

import unittest
from airflow.utils.email import get_email_address_list

EMAILS = ['test1@example.com', 'test2@example.com']


class EmailTest(unittest.TestCase):

    def test_get_email_address_single_email(self):
        emails_string = 'test1@example.com'

        self.assertEqual(
            get_email_address_list(emails_string), [emails_string])

    def test_get_email_address_comma_sep_string(self):
        emails_string = 'test1@example.com, test2@example.com'

        self.assertEqual(
            get_email_address_list(emails_string), EMAILS)

    def test_get_email_address_colon_sep_string(self):
        emails_string = 'test1@example.com; test2@example.com'

        self.assertEqual(
            get_email_address_list(emails_string), EMAILS)

    def test_get_email_address_list(self):
        emails_list = ['test1@example.com', 'test2@example.com']

        self.assertEqual(
            get_email_address_list(emails_list), EMAILS)

    def test_get_email_address_tuple(self):
        emails_tuple = ('test1@example.com', 'test2@example.com')

        self.assertEqual(
            get_email_address_list(emails_tuple), EMAILS)

    def test_get_email_address_invalid_type(self):
        emails_string = 1

        self.assertRaises(
            TypeError, get_email_address_list, emails_string)

    def test_get_email_address_invalid_type_in_iterable(self):
        emails_list = ['test1@example.com', 2]

        self.assertRaises(
            TypeError, get_email_address_list, emails_list)
