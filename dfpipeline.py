import json
from google.cloud import storage
from google.cloud import bigquery
from apache_beam.options.pipeline_options import WorkerOptions
import argparse, logging
import apache_beam as beam
import time
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.options.pipeline_options import SetupOptions
from apache_beam.options.pipeline_options import GoogleCloudOptions
from apache_beam.options.pipeline_options import StandardOptions
import requests
#from tenacity import *

class CustomParam(PipelineOptions):
    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_value_provider_argument('--url1', dest='url1', required=False, help='apiURL')
        parser.add_value_provider_argument('--gcsBucket', dest='gcsBucket', required=False, help='Bucket name')
        parser.add_value_provider_argument('--dataset', dest='dataset', required=False, help='bigquery dataset')
        parser.add_value_provider_argument('--tableID', dest='tableID', required=False, help='bigquery table name')
        #parser.add_value_provider_argument('--authKey', dest='authKey', required=False, help='api auth key')
        parser.add_value_provider_argument('--secretManagerID', dest='secretManagerID', required=False, help='api auth key')


#@retry(stop=stop_after_attempt(5), wait=wait_fixed(3))
class api_data(beam.DoFn) :
  def __init__(self):
    # TODO(BEAM-6158): Revert the workaround once we can pickle super() on py3.
    # super(WordExtractingDoFn, self).__init__()
    beam.DoFn.__init__(self)

  def process(self, element):
    try:
        #fetching data from public api
        url=str(custom_options.url1.get())
        logging.info("Fetching data from public api url:{}".format(url))
        logging.info("fetching from api")
        response_API = requests.get(url)
        #converting it to json object
        data = response_API.json()
        logging.info("fetched data:{}".format(data))
        return [data]
    except Exception as e:
        print("Failed to hit api:{} error is:{}".format(url,e))
        raise


class upload_blob(beam.DoFn) :
  def __init__(self):
    # TODO(BEAM-6158): Revert the workaround once we can pickle super() on py3.
    # super(WordExtractingDoFn, self).__init__()
    beam.DoFn.__init__(self)

  def process(self, element):
        try:
          """
          element:json object which we fetch from public api
          Uploads a json file to the bucket"""
          logging.info("json file:{}".format(element))
          bucket_name=str(custom_options.gcsBucket.get())
          print("bucket name:{}".format(bucket_name))
          destination_blob_name="external_api_data/ingested_data_{}.json".format(int(time.time()))
          logging.info("data uploading started at bucket path :gs://{}/{}".format(bucket_name,destination_blob_name))
          storage_client = storage.Client()
          bucket = storage_client.get_bucket(bucket_name)
          blob = bucket.blob(destination_blob_name)

          blob.upload_from_string(json.dumps(element))
          gcs_path="gs://{}/{}".format(bucket_name,destination_blob_name)
          return [gcs_path]
        except Exception as e:
            logging.error("Failed to upload data inside bucket:{}".format(e))


class gcs_to_bq(beam.DoFn) :
    def __init__(self):
        # TODO(BEAM-6158): Revert the workaround once we can pickle super() on py3.
        # super(WordExtractingDoFn, self).__init__()
        beam.DoFn.__init__(self)

    def process(self, element):
        try:
            """element:gcs json file path
               Uploading data from gcs to bigquery without auto schema"""

            projectID = "q-gcp-8566-nj-dhs-22-08"
            # Construct a BigQuery client object.
            client = bigquery.Client()
            dataset=str(custom_options.dataset.get())
            tableName=str(custom_options.tableID.get())
            table_id="{}.{}.{}".format(projectID,dataset,tableName)
            print(table_id)

            job_config = bigquery.LoadJobConfig(
                autodetect=True, source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
            )
            load_job = client.load_table_from_uri(
                element, table_id, job_config=job_config
            )
            load_job.result()
            destination_table = client.get_table(table_id)
            print("Loaded {} rows.".format(destination_table.num_rows))
        except Exception as e:
            logging.error("failed to ingest data in bigquery error is:{}".format(e))

def run(argv=None):
    global custom_options
    projectID="q-gcp-8566-nj-dhs-22-08"
    pipeline_options = PipelineOptions()
    custom_options = pipeline_options.view_as(CustomParam)
    google_cloud_options = pipeline_options.view_as(GoogleCloudOptions)
    google_cloud_options.job_name = "nj-dhs-ingestion-{}".format(int(time.time()))
    google_cloud_options.project = 'q-gcp-8566-nj-dhs-22-08'
    google_cloud_options.region = 'us-central1'
    google_cloud_options.staging_location = 'gs://csv_to_bigquery_load/Staging/'
    google_cloud_options.temp_location = 'gs://csv_to_bigquery_load/Temp/'
    pipeline_options.view_as(StandardOptions).runner = 'DataflowRunner'
    pipeline_options.view_as(StandardOptions).streaming = False
    setup_options = pipeline_options.view_as(SetupOptions)
    # setup_options.setup_file = './setup.py'
    setup_options.requirements_file = './requirements.txt'
    setup_options.save_main_session = True
    pipeline_options.view_as(
    WorkerOptions).subnetwork = "https://www.googleapis.com/compute/alpha/projects/q-gcp-8566-nj-dhs-22-08/regions/us-central1/subnetworks/subnet-1"
    p = beam.Pipeline(options=pipeline_options)
    results = (
        p
        |"Create Pipeline" >> beam.Create(["Start"])
        | 'fetch data from api' >> beam.ParDo(api_data())
        | 'upload data to bucket ' >> beam.ParDo(upload_blob())
        | 'Write to BigQuery' >>beam.ParDo(gcs_to_bq())
        | beam.Map(print))

    res=p.run()


if __name__ == '__main__':
  run()