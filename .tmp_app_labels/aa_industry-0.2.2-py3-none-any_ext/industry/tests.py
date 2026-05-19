from django.test import TestCase
from django.urls import reverse as r


#################
# injecting jobs
# job_details = dict()
# job_details['is_corp_job'] = False
# job_details['job_id'] = 123456
#
# a = EveEntity.objects.get_or_create_esi(id=56749)[0]
# job_details['blueprint_name'] = a.name
# job_details['blueprint_id'] = a.id
#
# job_details['activity_id'] = _get_activity_by_id(2)
#
# job_details['duration'] = 3600 * 2
# job_details['start_date'] = '2023-04-27T00:00:00Z'
# job_details['end_date'] = '2023-04-29T00:00:00Z'
# job_details['status'] = 'active'
# job_details['installer_id'] = user_id
# job_details['installer_portrait_url_32'] = character_portrait_url(user_id, 32)
# job_details['installer_portrait_url_64'] = character_portrait_url(user_id, 64)
# job_details['installer_portrait_url_128'] = character_portrait_url(user_id, 128)
# job_details['installer_portrait_url_256'] = character_portrait_url(user_id, 256)
# job_details['facility_id'] = '1041037509462'
#
# station = _get_structure(_request_headers, '1041037509462')
# if not station:
#     logger.error('error getting station')
#     job_details['station_name'] = ''
# else:
#     job_details['station_name'] = station.name
#
# return_list = list()
# return_list.append(job_details)
#
# return return_list
# end of injecting jobs


class ViewTest(TestCase):
    def setUp(self):
        self.resp = self.client.get(r('industry:index'))

    def test_index_requires_login(self):
        """
        GET /industry must require login
        """
        self.assertRedirects(self.resp, f'/account/login/?next={r("industry:index")}')

