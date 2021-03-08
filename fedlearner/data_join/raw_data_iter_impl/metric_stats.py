import copy
import random
from datetime import datetime

from fedlearner.common import metrics, common
from fedlearner.data_join.common import convert_to_str
from fedlearner.data_join.common import convert_to_iso_format


class MetricStats:
    def __init__(self, raw_data_options, metric_tags):
        self._tags = copy.deepcopy(metric_tags)
        self._stat_fields = raw_data_options.optional_fields
        self._sample_ratio = common.CONFIGS['raw_data_metrics_sample_rate']

    def emit_metric(self, item):
        if random.random() < self._sample_ratio:
            tags = copy.deepcopy(self._tags)
            for field in self._stat_fields:
                value = convert_to_str(getattr(item, field, '#None#'))
                tags[field] = value
            tags['example_id'] = convert_to_str(item.example_id)
            tags['event_time'] = convert_to_iso_format(item.event_time)
            tags['process_time'] = convert_to_iso_format(datetime.now())
            metrics.emit_store(name='input_data', value=0, tags=tags)
