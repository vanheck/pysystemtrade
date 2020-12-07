from sysdata.mongodb.mongo_connection import mongoConnection, mongoDb
from sysdata.mongodb.mongo_generic import mongoData, MONGO_ID_KEY, existingData
from syscore.dateutils import long_to_datetime, datetime_to_long

from syslogdiag.log import logEntry, TIMESTAMP_ID, LEVEL_ID, TEXT_ID, LOG_RECORD_ID, logtoscreen
from syslogdiag.database_log import logToDb, logData
from copy import copy
import datetime

LOG_COLLECTION_NAME = "Logs"
EMAIL_ON_LOG_LEVEL = [4]


class logToMongod(logToDb):
    """
    Logs to a mongodb

    """

    def __init__(
        self,
        type: str,
        data=None,
        log_level: str="Off",
        mongo_db: mongoDb=None,
        **kwargs,
    ):
        super().__init__(type=type, log_level=log_level, **kwargs)
        self._mongo_data = mongoData(LOG_COLLECTION_NAME, LOG_RECORD_ID, mongo_db=mongo_db)
        self._delete_old_metadata()

    def _delete_old_metadata(self):
        ## ONLY NEED TO DO ONCE... CHANGED THE WAY THIS WORKS
        self.mongo_data._mongo.collection.delete_one(dict(_meta_data='log_id'))
        self.mongo_data._mongo.collection.drop_indexes()

    @property
    def mongo_data(self):
        return self._mongo_data

    def get_last_used_log_id(self) -> int:
        """
        Get last used log id. Returns None if not present

        :return: int or None
        """
        all_log_ids = self.get_all_log_ids()
        if len(all_log_ids)==0:
            return None

        return max(all_log_ids)

    def get_all_log_ids(self) -> list:
        return self.mongo_data.get_list_of_keys()

    def update_log_id(self, next_id: int):
        self.mongo_data.add_data(next_id, {}, allow_overwrite=True)

    def add_log_record(self, log_entry):
        record_as_dict = log_entry.log_dict()
        key = record_as_dict[LOG_RECORD_ID]

        self.mongo_data.add_data(key, record_as_dict, allow_overwrite=True)


class mongoLogData(logData):
    # Need to change so uses data
    def __init__(self, mongo_db=None, log=logtoscreen("mongoLogData")):
        self._mongo_data = mongoData(LOG_COLLECTION_NAME, LOG_RECORD_ID, mongo_db=mongo_db)
        super().__init__(log=log)

    @property
    def mongo_data(self):
        return self._mongo_data

    def get_log_items_as_entries(self, attribute_dict=dict(), lookback_days=1):
        """
        Return log items not as text, good for diagnostics

        :param attribute_dict: dictionary of attributes to return logs for
        :return: list of 4-typles: timestamp, level, text, attributes
        """

        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=lookback_days)
        timestamp_dict = {}
        timestamp_dict["$gt"] = datetime_to_long(cutoff_date)
        attribute_dict[TIMESTAMP_ID] = timestamp_dict

        ## FIXME SHOULDN'T ACCESS THIS DIRECTLY
        result_dict = self.mongo_data._mongo.collection.find(attribute_dict)
        # from cursor to list...
        results_list = [single_log_dict for single_log_dict in result_dict]

        # ... to list of log entries
        results = [
            mongoLogEntry.log_entry_from_dict(single_log_dict)
            for single_log_dict in results_list
        ]

        # sort by log ID
        results.sort(key=lambda x: x._log_id)

        return results

    def delete_log_items_from_before_n_days(self, days=365):
        # need something to delete old log records, eg more than x months ago

        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        attribute_dict = {}
        timestamp_dict = {}
        timestamp_dict["$lt"] = datetime_to_long(cutoff_date)
        attribute_dict[TIMESTAMP_ID] = timestamp_dict

        # FIXME
        self._mongo_data._mongo.collection.remove(attribute_dict)


class mongoLogEntry(logEntry):
    @classmethod
    def log_entry_from_dict(logEntry, log_dict_input):
        """
        Starting with the dictionary representation, recover the original logEntry

        :param log_dict: dict, as per logEntry.log_dict()
        :return: logEntry object
        """
        log_dict = copy(log_dict_input)
        log_dict.pop(MONGO_ID_KEY)
        log_timestamp_aslong = log_dict.pop(TIMESTAMP_ID)
        msg_level = log_dict.pop(LEVEL_ID)
        text = log_dict.pop(TEXT_ID)
        log_id = log_dict.pop(LOG_RECORD_ID)
        input_attributes = log_dict

        log_timestamp = long_to_datetime(log_timestamp_aslong)

        log_entry = logEntry(
            text,
            log_timestamp=log_timestamp,
            msglevel=msg_level,
            input_attributes=input_attributes,
            log_id=log_id,
        )

        return log_entry
