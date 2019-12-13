#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from mock import call, patch
from ns1.rest.errors import AuthException, RateLimitException, \
    ResourceException
from six import text_type
from unittest import TestCase

from octodns.record import Delete, Record, Update
from octodns.provider.ns1 import Ns1Client, Ns1Provider
from octodns.zone import Zone


class TestNs1Provider(TestCase):
    zone = Zone('unit.tests.', [])
    expected = set()
    expected.add(Record.new(zone, '', {
        'ttl': 32,
        'type': 'A',
        'value': '1.2.3.4',
        'meta': {},
    }))
    expected.add(Record.new(zone, 'foo', {
        'ttl': 33,
        'type': 'A',
        'values': ['1.2.3.4', '1.2.3.5'],
        'meta': {},
    }))
    expected.add(Record.new(zone, 'geo', {
        'ttl': 34,
        'type': 'A',
        'values': ['101.102.103.104', '101.102.103.105'],
        'geo': {'NA-US-NY': ['201.202.203.204']},
        'meta': {},
    }))
    expected.add(Record.new(zone, 'cname', {
        'ttl': 34,
        'type': 'CNAME',
        'value': 'foo.unit.tests.',
    }))
    expected.add(Record.new(zone, '', {
        'ttl': 35,
        'type': 'MX',
        'values': [{
            'preference': 10,
            'exchange': 'mx1.unit.tests.',
        }, {
            'preference': 20,
            'exchange': 'mx2.unit.tests.',
        }]
    }))
    expected.add(Record.new(zone, 'naptr', {
        'ttl': 36,
        'type': 'NAPTR',
        'values': [{
            'flags': 'U',
            'order': 100,
            'preference': 100,
            'regexp': '!^.*$!sip:info@bar.example.com!',
            'replacement': '.',
            'service': 'SIP+D2U',
        }, {
            'flags': 'S',
            'order': 10,
            'preference': 100,
            'regexp': '!^.*$!sip:info@bar.example.com!',
            'replacement': '.',
            'service': 'SIP+D2U',
        }]
    }))
    expected.add(Record.new(zone, '', {
        'ttl': 37,
        'type': 'NS',
        'values': ['ns1.unit.tests.', 'ns2.unit.tests.'],
    }))
    expected.add(Record.new(zone, '_srv._tcp', {
        'ttl': 38,
        'type': 'SRV',
        'values': [{
            'priority': 10,
            'weight': 20,
            'port': 30,
            'target': 'foo-1.unit.tests.',
        }, {
            'priority': 12,
            'weight': 30,
            'port': 30,
            'target': 'foo-2.unit.tests.',
        }]
    }))
    expected.add(Record.new(zone, 'sub', {
        'ttl': 39,
        'type': 'NS',
        'values': ['ns3.unit.tests.', 'ns4.unit.tests.'],
    }))
    expected.add(Record.new(zone, '', {
        'ttl': 40,
        'type': 'CAA',
        'value': {
            'flags': 0,
            'tag': 'issue',
            'value': 'ca.unit.tests',
        },
    }))

    ns1_records = [{
        'type': 'A',
        'ttl': 32,
        'short_answers': ['1.2.3.4'],
        'domain': 'unit.tests.',
    }, {
        'type': 'A',
        'ttl': 33,
        'short_answers': ['1.2.3.4', '1.2.3.5'],
        'domain': 'foo.unit.tests.',
    }, {
        'type': 'A',
        'ttl': 34,
        'short_answers': ['101.102.103.104', '101.102.103.105'],
        'domain': 'geo.unit.tests',
    }, {
        'type': 'CNAME',
        'ttl': 34,
        'short_answers': ['foo.unit.tests'],
        'domain': 'cname.unit.tests.',
    }, {
        'type': 'MX',
        'ttl': 35,
        'short_answers': ['10 mx1.unit.tests.', '20 mx2.unit.tests'],
        'domain': 'unit.tests.',
    }, {
        'type': 'NAPTR',
        'ttl': 36,
        'short_answers': [
            '10 100 S SIP+D2U !^.*$!sip:info@bar.example.com! .',
            '100 100 U SIP+D2U !^.*$!sip:info@bar.example.com! .'
        ],
        'domain': 'naptr.unit.tests.',
    }, {
        'type': 'NS',
        'ttl': 37,
        'short_answers': ['ns1.unit.tests.', 'ns2.unit.tests'],
        'domain': 'unit.tests.',
    }, {
        'type': 'SRV',
        'ttl': 38,
        'short_answers': ['12 30 30 foo-2.unit.tests.',
                          '10 20 30 foo-1.unit.tests'],
        'domain': '_srv._tcp.unit.tests.',
    }, {
        'type': 'NS',
        'ttl': 39,
        'short_answers': ['ns3.unit.tests.', 'ns4.unit.tests'],
        'domain': 'sub.unit.tests.',
    }, {
        'type': 'CAA',
        'ttl': 40,
        'short_answers': ['0 issue ca.unit.tests'],
        'domain': 'unit.tests.',
    }]

    @patch('ns1.rest.records.Records.retrieve')
    @patch('ns1.rest.zones.Zones.retrieve')
    def test_populate(self, zone_retrieve_mock, record_retrieve_mock):
        provider = Ns1Provider('test', 'api-key')

        # Bad auth
        zone_retrieve_mock.side_effect = AuthException('unauthorized')
        zone = Zone('unit.tests.', [])
        with self.assertRaises(AuthException) as ctx:
            provider.populate(zone)
        self.assertEquals(zone_retrieve_mock.side_effect, ctx.exception)

        # General error
        zone_retrieve_mock.reset_mock()
        zone_retrieve_mock.side_effect = ResourceException('boom')
        zone = Zone('unit.tests.', [])
        with self.assertRaises(ResourceException) as ctx:
            provider.populate(zone)
        self.assertEquals(zone_retrieve_mock.side_effect, ctx.exception)
        self.assertEquals(('unit.tests',), zone_retrieve_mock.call_args[0])

        # Non-existent zone doesn't populate anything
        zone_retrieve_mock.reset_mock()
        zone_retrieve_mock.side_effect = \
            ResourceException('server error: zone not found')
        zone = Zone('unit.tests.', [])
        exists = provider.populate(zone)
        self.assertEquals(set(), zone.records)
        self.assertEquals(('unit.tests',), zone_retrieve_mock.call_args[0])
        self.assertFalse(exists)

        # Existing zone w/o records
        zone_retrieve_mock.reset_mock()
        record_retrieve_mock.reset_mock()
        ns1_zone = {
            'records': [{
                "domain": "geo.unit.tests",
                "zone": "unit.tests",
                "type": "A",
                "answers": [
                    {'answer': ['1.1.1.1'], 'meta': {}},
                    {'answer': ['1.2.3.4'],
                     'meta': {'ca_province': ['ON']}},
                    {'answer': ['2.3.4.5'], 'meta': {'us_state': ['NY']}},
                    {'answer': ['3.4.5.6'], 'meta': {'country': ['US']}},
                    {'answer': ['4.5.6.7'],
                     'meta': {'iso_region_code': ['NA-US-WA']}},
                ],
                'tier': 3,
                'ttl': 34,
            }],
        }
        zone_retrieve_mock.side_effect = [ns1_zone]
        # Its tier 3 so we'll do a full lookup
        record_retrieve_mock.side_effect = ns1_zone['records']
        zone = Zone('unit.tests.', [])
        provider.populate(zone)
        self.assertEquals(1, len(zone.records))
        self.assertEquals(('unit.tests',), zone_retrieve_mock.call_args[0])
        record_retrieve_mock.assert_has_calls([call('unit.tests',
                                                    'geo.unit.tests', 'A')])

        # Existing zone w/records
        zone_retrieve_mock.reset_mock()
        record_retrieve_mock.reset_mock()
        ns1_zone = {
            'records': self.ns1_records + [{
                "domain": "geo.unit.tests",
                "zone": "unit.tests",
                "type": "A",
                "answers": [
                    {'answer': ['1.1.1.1'], 'meta': {}},
                    {'answer': ['1.2.3.4'],
                     'meta': {'ca_province': ['ON']}},
                    {'answer': ['2.3.4.5'], 'meta': {'us_state': ['NY']}},
                    {'answer': ['3.4.5.6'], 'meta': {'country': ['US']}},
                    {'answer': ['4.5.6.7'],
                     'meta': {'iso_region_code': ['NA-US-WA']}},
                ],
                'tier': 3,
                'ttl': 34,
            }],
        }
        zone_retrieve_mock.side_effect = [ns1_zone]
        # Its tier 3 so we'll do a full lookup
        record_retrieve_mock.side_effect = ns1_zone['records']
        zone = Zone('unit.tests.', [])
        provider.populate(zone)
        self.assertEquals(self.expected, zone.records)
        self.assertEquals(('unit.tests',), zone_retrieve_mock.call_args[0])
        record_retrieve_mock.assert_has_calls([call('unit.tests',
                                                    'geo.unit.tests', 'A')])

        # Test skipping unsupported record type
        zone_retrieve_mock.reset_mock()
        record_retrieve_mock.reset_mock()
        ns1_zone = {
            'records': self.ns1_records + [{
                'type': 'UNSUPPORTED',
                'ttl': 42,
                'short_answers': ['unsupported'],
                'domain': 'unsupported.unit.tests.',
            }, {
                "domain": "geo.unit.tests",
                "zone": "unit.tests",
                "type": "A",
                "answers": [
                    {'answer': ['1.1.1.1'], 'meta': {}},
                    {'answer': ['1.2.3.4'],
                     'meta': {'ca_province': ['ON']}},
                    {'answer': ['2.3.4.5'], 'meta': {'us_state': ['NY']}},
                    {'answer': ['3.4.5.6'], 'meta': {'country': ['US']}},
                    {'answer': ['4.5.6.7'],
                     'meta': {'iso_region_code': ['NA-US-WA']}},
                ],
                'tier': 3,
                'ttl': 34,
            }],
        }
        zone_retrieve_mock.side_effect = [ns1_zone]
        zone = Zone('unit.tests.', [])
        provider.populate(zone)
        self.assertEquals(self.expected, zone.records)
        self.assertEquals(('unit.tests',), zone_retrieve_mock.call_args[0])
        record_retrieve_mock.assert_has_calls([call('unit.tests',
                                                    'geo.unit.tests', 'A')])

    @patch('ns1.rest.records.Records.delete')
    @patch('ns1.rest.records.Records.update')
    @patch('ns1.rest.records.Records.create')
    @patch('ns1.rest.records.Records.retrieve')
    @patch('ns1.rest.zones.Zones.create')
    @patch('ns1.rest.zones.Zones.retrieve')
    def test_sync(self, zone_retrieve_mock, zone_create_mock,
                  record_retrieve_mock, record_create_mock,
                  record_update_mock, record_delete_mock):
        provider = Ns1Provider('test', 'api-key')

        desired = Zone('unit.tests.', [])
        for r in self.expected:
            desired.add_record(r)

        plan = provider.plan(desired)
        # everything except the root NS
        expected_n = len(self.expected) - 1
        self.assertEquals(expected_n, len(plan.changes))
        self.assertTrue(plan.exists)

        # Fails, general error
        zone_retrieve_mock.reset_mock()
        zone_create_mock.reset_mock()
        zone_retrieve_mock.side_effect = ResourceException('boom')
        with self.assertRaises(ResourceException) as ctx:
            provider.apply(plan)
        self.assertEquals(zone_retrieve_mock.side_effect, ctx.exception)

        # Fails, bad auth
        zone_retrieve_mock.reset_mock()
        zone_create_mock.reset_mock()
        zone_retrieve_mock.side_effect = \
            ResourceException('server error: zone not found')
        zone_create_mock.side_effect = AuthException('unauthorized')
        with self.assertRaises(AuthException) as ctx:
            provider.apply(plan)
        self.assertEquals(zone_create_mock.side_effect, ctx.exception)

        # non-existent zone, create
        zone_retrieve_mock.reset_mock()
        zone_create_mock.reset_mock()
        zone_retrieve_mock.side_effect = \
            ResourceException('server error: zone not found')

        zone_create_mock.side_effect = ['foo']
        # Test out the create rate-limit handling, then 9 successes
        record_create_mock.side_effect = [
            RateLimitException('boo', period=0),
        ] + ([None] * 9)

        got_n = provider.apply(plan)
        self.assertEquals(expected_n, got_n)

        # Zone was created
        zone_create_mock.assert_has_calls([call('unit.tests')])
        # Checking that we got some of the expected records too
        record_create_mock.assert_has_calls([
            call('unit.tests', 'unit.tests', 'A', answers=[
                {'answer': ['1.2.3.4'], 'meta': {}}
            ], filters=[], ttl=32),
            call('unit.tests', 'unit.tests', 'CAA', answers=[
                (0, 'issue', 'ca.unit.tests')
            ], ttl=40),
            call('unit.tests', 'unit.tests', 'MX', answers=[
                (10, 'mx1.unit.tests.'), (20, 'mx2.unit.tests.')
            ], ttl=35),
        ])

        # Update & delete
        zone_retrieve_mock.reset_mock()
        zone_create_mock.reset_mock()

        ns1_zone = {
            'records': self.ns1_records + [{
                'type': 'A',
                'ttl': 42,
                'short_answers': ['9.9.9.9'],
                'domain': 'delete-me.unit.tests.',
            }, {
                "domain": "geo.unit.tests",
                "zone": "unit.tests",
                "type": "A",
                "short_answers": [
                    '1.1.1.1',
                    '1.2.3.4',
                    '2.3.4.5',
                    '3.4.5.6',
                    '4.5.6.7',
                ],
                'tier': 3,  # This flags it as advacned, full load required
                'ttl': 34,
            }],
        }
        ns1_zone['records'][0]['short_answers'][0] = '2.2.2.2'

        record_retrieve_mock.side_effect = [{
            "domain": "geo.unit.tests",
            "zone": "unit.tests",
            "type": "A",
            "answers": [
                {'answer': ['1.1.1.1'], 'meta': {}},
                {'answer': ['1.2.3.4'],
                 'meta': {'ca_province': ['ON']}},
                {'answer': ['2.3.4.5'], 'meta': {'us_state': ['NY']}},
                {'answer': ['3.4.5.6'], 'meta': {'country': ['US']}},
                {'answer': ['4.5.6.7'],
                 'meta': {'iso_region_code': ['NA-US-WA']}},
            ],
            'tier': 3,
            'ttl': 34,
        }]

        zone_retrieve_mock.side_effect = [ns1_zone, ns1_zone]
        plan = provider.plan(desired)
        self.assertEquals(3, len(plan.changes))
        # Shouldn't rely on order so just count classes
        classes = defaultdict(lambda: 0)
        for change in plan.changes:
            classes[change.__class__] += 1
        self.assertEquals(1, classes[Delete])
        self.assertEquals(2, classes[Update])

        record_update_mock.side_effect = [
            RateLimitException('one', period=0),
            None,
            None,
        ]
        record_delete_mock.side_effect = [
            RateLimitException('two', period=0),
            None,
            None,
        ]

        got_n = provider.apply(plan)
        self.assertEquals(3, got_n)

        record_update_mock.assert_has_calls([
            call('unit.tests', 'unit.tests', 'A', answers=[
                {'answer': ['1.2.3.4'], 'meta': {}}],
                filters=[],
                ttl=32),
            call('unit.tests', 'unit.tests', 'A', answers=[
                {'answer': ['1.2.3.4'], 'meta': {}}],
                filters=[],
                ttl=32),
            call('unit.tests', 'geo.unit.tests', 'A', answers=[
                {'answer': ['101.102.103.104'], 'meta': {}},
                {'answer': ['101.102.103.105'], 'meta': {}},
                {
                    'answer': ['201.202.203.204'],
                    'meta': {'iso_region_code': ['NA-US-NY']}
                }],
                filters=[
                    {'filter': 'shuffle', 'config': {}},
                    {'filter': 'geotarget_country', 'config': {}},
                    {'filter': 'select_first_n', 'config': {'N': 1}}],
                ttl=34)
        ])

    def test_escaping(self):
        provider = Ns1Provider('test', 'api-key')
        record = {
            'ttl': 31,
            'short_answers': ['foo; bar baz; blip']
        }
        self.assertEquals(['foo\\; bar baz\\; blip'],
                          provider._data_for_SPF('SPF', record)['values'])

        record = {
            'ttl': 31,
            'short_answers': ['no', 'foo; bar baz; blip', 'yes']
        }
        self.assertEquals(['no', 'foo\\; bar baz\\; blip', 'yes'],
                          provider._data_for_TXT('TXT', record)['values'])

        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'spf', {
            'ttl': 34,
            'type': 'SPF',
            'value': 'foo\\; bar baz\\; blip'
        })
        params, _ = provider._params_for_SPF(record)
        self.assertEquals(['foo; bar baz; blip'], params['answers'])

        record = Record.new(zone, 'txt', {
            'ttl': 35,
            'type': 'TXT',
            'value': 'foo\\; bar baz\\; blip'
        })
        params, _ = provider._params_for_SPF(record)
        self.assertEquals(['foo; bar baz; blip'], params['answers'])

    def test_data_for_CNAME(self):
        provider = Ns1Provider('test', 'api-key')

        # answers from ns1
        a_record = {
            'ttl': 31,
            'type': 'CNAME',
            'short_answers': ['foo.unit.tests.']
        }
        a_expected = {
            'ttl': 31,
            'type': 'CNAME',
            'value': 'foo.unit.tests.'
        }
        self.assertEqual(a_expected,
                         provider._data_for_CNAME(a_record['type'], a_record))

        # no answers from ns1
        b_record = {
            'ttl': 32,
            'type': 'CNAME',
            'short_answers': []
        }
        b_expected = {
            'ttl': 32,
            'type': 'CNAME',
            'value': None
        }
        self.assertEqual(b_expected,
                         provider._data_for_CNAME(b_record['type'], b_record))


class TestNs1ProviderDynamic(TestCase):
    zone = Zone('unit.tests.', [])

    record = Record.new(zone, '', {
        'dynamic': {
            'pools': {
                'iad': {
                    'values': [{
                        'value': '1.2.3.4',
                    }, {
                        'value': '2.3.4.5',
                    }],
                },
            },
            'rules': [{
                'pool': 'iad',
            }],
        },
        'octodns': {
            'healthcheck': {
                'host': 'send.me',
                'path': '/_ping',
                'port': 80,
                'protocol': 'HTTP',
            }
        },
        'ttl': 32,
        'type': 'A',
        'value': '1.2.3.4',
        'meta': {},
    })

    def test_notes(self):
        provider = Ns1Provider('test', 'api-key')

        self.assertEquals({}, provider._parse_notes(None))
        self.assertEquals({}, provider._parse_notes(''))
        self.assertEquals({}, provider._parse_notes('blah-blah-blah'))

        # Round tripping
        data = {
            'key': 'value',
            'priority': '1',
        }
        notes = provider._encode_notes(data)
        self.assertEquals(data, provider._parse_notes(notes))

    def test_monitors_for(self):
        provider = Ns1Provider('test', 'api-key')

        # pre-populate the client's monitors cache
        monitor_one = {
            'config': {
                'host': '1.2.3.4',
            },
            'notes': 'host:unit.tests type:A',
        }
        monitor_four = {
            'config': {
                'host': '2.3.4.5',
            },
            'notes': 'host:unit.tests type:A',
        }
        provider._client._monitors_cache = {
            'one': monitor_one,
            'two': {
                'config': {
                    'host': '8.8.8.8',
                },
                'notes': 'host:unit.tests type:AAAA',
            },
            'three': {
                'config': {
                    'host': '9.9.9.9',
                },
                'notes': 'host:other.unit.tests type:A',
            },
            'four': monitor_four,
        }

        # Would match, but won't get there b/c it's not dynamic
        record = Record.new(self.zone, '', {
            'ttl': 32,
            'type': 'A',
            'value': '1.2.3.4',
            'meta': {},
        })
        self.assertEquals({}, provider._monitors_for(record))

        # Will match some records
        self.assertEquals({
            '1.2.3.4': monitor_one,
            '2.3.4.5': monitor_four,
        }, provider._monitors_for(self.record))

    def test_uuid(self):
        # Just a smoke test/for coverage
        provider = Ns1Provider('test', 'api-key')
        self.assertTrue(provider._uuid())

    @patch('octodns.provider.ns1.Ns1Provider._uuid')
    @patch('ns1.rest.data.Feed.create')
    def test_create_feed(self, datafeed_create_mock, uuid_mock):
        provider = Ns1Provider('test', 'api-key')

        # pre-fill caches to avoid extranious calls (things we're testing
        # elsewhere)
        provider._client._datasource_id = 'foo'
        provider._client._feeds_for_monitors = {}

        uuid_mock.reset_mock()
        datafeed_create_mock.reset_mock()
        uuid_mock.side_effect = ['xxxxxxxxxxxxxx']
        feed = {
            'id': 'feed',
        }
        datafeed_create_mock.side_effect = [feed]
        monitor = {
            'id': 'one',
            'name': 'one name',
            'config': {
                'host': '1.2.3.4',
            },
            'notes': 'host:unit.tests type:A',
        }
        self.assertEquals('feed', provider._create_feed(monitor))
        datafeed_create_mock.assert_has_calls([call('foo', 'one name - xxxxxx',
                                                    {'jobid': 'one'})])

    @patch('octodns.provider.ns1.Ns1Provider._create_feed')
    @patch('octodns.provider.ns1.Ns1Client.monitors_create')
    @patch('octodns.provider.ns1.Ns1Client.notifylists_create')
    def test_create_monitor(self, notifylists_create_mock,
                            monitors_create_mock, create_feed_mock):
        provider = Ns1Provider('test', 'api-key')

        # pre-fill caches to avoid extranious calls (things we're testing
        # elsewhere)
        provider._client._datasource_id = 'foo'
        provider._client._feeds_for_monitors = {}

        notifylists_create_mock.reset_mock()
        monitors_create_mock.reset_mock()
        create_feed_mock.reset_mock()
        notifylists_create_mock.side_effect = [{
            'id': 'nl-id',
        }]
        monitors_create_mock.side_effect = [{
            'id': 'mon-id',
        }]
        create_feed_mock.side_effect = ['feed-id']
        monitor = {
            'name': 'test monitor',
        }
        monitor_id, feed_id = provider._create_monitor(monitor)
        self.assertEquals('mon-id', monitor_id)
        self.assertEquals('feed-id', feed_id)
        monitors_create_mock.assert_has_calls([call(name='test monitor',
                                                    notify_list='nl-id')])

    def test_monitor_gen(self):
        provider = Ns1Provider('test', 'api-key')

        value = '3.4.5.6'
        monitor = provider._monitor_gen(self.record, value)
        self.assertEquals(value, monitor['config']['host'])
        self.assertTrue('\\nHost: send.me\\r' in monitor['config']['send'])
        self.assertFalse(monitor['config']['ssl'])
        self.assertEquals('host:unit.tests type:A', monitor['notes'])

        self.record._octodns['healthcheck']['protocol'] = 'HTTPS'
        monitor = provider._monitor_gen(self.record, value)
        self.assertTrue(monitor['config']['ssl'])


class TestNs1Client(TestCase):

    @patch('ns1.rest.zones.Zones.retrieve')
    def test_retry_behavior(self, zone_retrieve_mock):
        client = Ns1Client('dummy-key')

        # No retry required, just calls and is returned
        zone_retrieve_mock.reset_mock()
        zone_retrieve_mock.side_effect = ['foo']
        self.assertEquals('foo', client.zones_retrieve('unit.tests'))
        zone_retrieve_mock.assert_has_calls([call('unit.tests')])

        # One retry required
        zone_retrieve_mock.reset_mock()
        zone_retrieve_mock.side_effect = [
            RateLimitException('boo', period=0),
            'foo'
        ]
        self.assertEquals('foo', client.zones_retrieve('unit.tests'))
        zone_retrieve_mock.assert_has_calls([call('unit.tests')])

        # Two retries required
        zone_retrieve_mock.reset_mock()
        zone_retrieve_mock.side_effect = [
            RateLimitException('boo', period=0),
            'foo'
        ]
        self.assertEquals('foo', client.zones_retrieve('unit.tests'))
        zone_retrieve_mock.assert_has_calls([call('unit.tests')])

        # Exhaust our retries
        zone_retrieve_mock.reset_mock()
        zone_retrieve_mock.side_effect = [
            RateLimitException('first', period=0),
            RateLimitException('boo', period=0),
            RateLimitException('boo', period=0),
            RateLimitException('last', period=0),
        ]
        with self.assertRaises(RateLimitException) as ctx:
            client.zones_retrieve('unit.tests')
        self.assertEquals('last', text_type(ctx.exception))

    @patch('ns1.rest.data.Source.list')
    @patch('ns1.rest.data.Source.create')
    def test_datasource_id(self, datasource_create_mock, datasource_list_mock):
        client = Ns1Client('dummy-key')

        # First invocation with an empty list create
        datasource_list_mock.reset_mock()
        datasource_create_mock.reset_mock()
        datasource_list_mock.side_effect = [[]]
        datasource_create_mock.side_effect = [{
            'id': 'foo',
        }]
        self.assertEquals('foo', client.datasource_id)
        name = 'octoDNS NS1 Data Source'
        source_type = 'nsone_monitoring'
        datasource_create_mock.assert_has_calls([call(name=name,
                                                      sourcetype=source_type)])
        datasource_list_mock.assert_called_once()

        # 2nd invocation is cached
        datasource_list_mock.reset_mock()
        datasource_create_mock.reset_mock()
        self.assertEquals('foo', client.datasource_id)
        datasource_create_mock.assert_not_called()
        datasource_list_mock.assert_not_called()

        # Reset the client's cache
        client._datasource_id = None

        # First invocation with a match in the list finds it and doesn't call
        # create
        datasource_list_mock.reset_mock()
        datasource_create_mock.reset_mock()
        datasource_list_mock.side_effect = [[{
            'id': 'other',
            'name': 'not a match',
        }, {
            'id': 'bar',
            'name': name,
        }]]
        self.assertEquals('bar', client.datasource_id)
        datasource_create_mock.assert_not_called()
        datasource_list_mock.assert_called_once()

    @patch('ns1.rest.data.Feed.delete')
    @patch('ns1.rest.data.Feed.create')
    @patch('ns1.rest.data.Feed.list')
    def test_feeds_for_monitors(self, datafeed_list_mock,
                                datafeed_create_mock,
                                datafeed_delete_mock):
        client = Ns1Client('dummy-key')

        # pre-cache datasource_id
        client._datasource_id = 'foo'

        # Populate the cache and check the results
        datafeed_list_mock.reset_mock()
        datafeed_list_mock.side_effect = [[{
            'config': {
                'jobid': 'the-job',
            },
            'id': 'the-feed',
        }, {
            'config': {
                'jobid': 'the-other-job',
            },
            'id': 'the-other-feed',
        }]]
        expected = {
            'the-job': 'the-feed',
            'the-other-job': 'the-other-feed',
        }
        self.assertEquals(expected, client.feeds_for_monitors)
        datafeed_list_mock.assert_called_once()

        # 2nd call uses cache
        datafeed_list_mock.reset_mock()
        self.assertEquals(expected, client.feeds_for_monitors)
        datafeed_list_mock.assert_not_called()

        # create a feed and make sure it's in the cache/map
        datafeed_create_mock.reset_mock()
        datafeed_create_mock.side_effect = [{
            'id': 'new-feed',
        }]
        client.datafeed_create(client.datasource_id, 'new-name', {
            'jobid': 'new-job',
        })
        datafeed_create_mock.assert_has_calls([call('foo', 'new-name', {
            'jobid': 'new-job',
        })])
        new_expected = expected.copy()
        new_expected['new-job'] = 'new-feed'
        self.assertEquals(new_expected, client.feeds_for_monitors)
        datafeed_create_mock.assert_called_once()

        # Delete a feed and make sure it's out of the cache/map
        datafeed_delete_mock.reset_mock()
        client.datafeed_delete(client.datasource_id, 'new-feed')
        self.assertEquals(expected, client.feeds_for_monitors)
        datafeed_delete_mock.assert_called_once()

    @patch('ns1.rest.monitoring.Monitors.delete')
    @patch('ns1.rest.monitoring.Monitors.update')
    @patch('ns1.rest.monitoring.Monitors.create')
    @patch('ns1.rest.monitoring.Monitors.list')
    def test_monitors(self, monitors_list_mock, monitors_create_mock,
                      monitors_update_mock, monitors_delete_mock):
        client = Ns1Client('dummy-key')

        one = {
            'id': 'one',
            'key': 'value',
        }
        two = {
            'id': 'two',
            'key': 'other-value',
        }

        # Populate the cache and check the results
        monitors_list_mock.reset_mock()
        monitors_list_mock.side_effect = [[one, two]]
        expected = {
            'one': one,
            'two': two,
        }
        self.assertEquals(expected, client.monitors)
        monitors_list_mock.assert_called_once()

        # 2nd round pulls it from cache
        monitors_list_mock.reset_mock()
        self.assertEquals(expected, client.monitors)
        monitors_list_mock.assert_not_called()

        # Create a monitor, make sure it's in the list
        monitors_create_mock.reset_mock()
        monitor = {
            'id': 'new-id',
            'key': 'new-value',
        }
        monitors_create_mock.side_effect = [monitor]
        self.assertEquals(monitor, client.monitors_create(param='eter'))
        monitors_create_mock.assert_has_calls([call({}, param='eter')])
        new_expected = expected.copy()
        new_expected['new-id'] = monitor
        self.assertEquals(new_expected, client.monitors)

        # Update a monitor, make sure it's updated in the cache
        monitors_update_mock.reset_mock()
        monitor = {
            'id': 'new-id',
            'key': 'changed-value',
        }
        monitors_update_mock.side_effect = [monitor]
        self.assertEquals(monitor, client.monitors_update('new-id',
                                                          key='changed-value'))
        monitors_update_mock \
            .assert_has_calls([call('new-id', {}, key='changed-value')])
        new_expected['new-id'] = monitor
        self.assertEquals(new_expected, client.monitors)

        # Delete a monitor, make sure it's out of the list
        monitors_delete_mock.reset_mock()
        monitors_delete_mock.side_effect = ['deleted']
        self.assertEquals('deleted', client.monitors_delete('new-id'))
        monitors_delete_mock.assert_has_calls([call('new-id')])
        self.assertEquals(expected, client.monitors)
