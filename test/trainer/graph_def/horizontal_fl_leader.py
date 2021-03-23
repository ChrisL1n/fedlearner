# Copyright 2020 The FedLearner Authors. All Rights Reserved.
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

# coding: utf-8
# pylint: disable=no-else-return, inconsistent-return-statements

import logging
import tensorflow.compat.v1 as tf
import fedlearner.trainer as flt


def input_fn(bridge, trainer_master):
    def parse_fn(example):
        feature_map = {
            "example_id": tf.FixedLenFeature([], tf.string),
            "x": tf.FixedLenFeature([261], tf.float32),
        }
        features = tf.parse_example(example, features=feature_map)
        return features, {}
    batch = 2
    loader0 = flt.data.DataBlockLoaderV2('leader', bridge,
                                         trainer_master,
                                         'test-liuqi-mnist-leader-v1')
    loader1 = flt.data.DataBlockLoaderV2('leader', bridge, trainer_master,
                                         "test-liuqi-mnist-local")
    block_count0 = loader0.block_count
    block_count1 = loader1.block_count
    min_block_count = min(block_count0, block_count1)
    batch_size0 = batch * (block_count0 // min_block_count)
    batch_size1 = batch * (block_count1 // min_block_count)

    dataset = loader0.make_dataset(batch_size0)
    dataset = dataset.map(map_func=parse_fn,
        num_parallel_calls=tf.data.experimental.AUTOTUNE)
    features, label = dataset.make_one_shot_iterator().get_next()

    def parse_fn1(example):
        feature_map = {
            "x": tf.FixedLenFeature([261], tf.float32),
        }
        features = tf.parse_example(example, features=feature_map)
        return features, {}
    dataset = loader1.make_dataset(batch_size1)
    dataset = dataset.map(map_func=parse_fn1,
                          num_parallel_calls=tf.data.experimental.AUTOTUNE)
    features1, _ = dataset.make_one_shot_iterator().get_next()
    features['x1'] = features1['x']

    return features, label


def serving_input_receiver_fn():
    feature_map = {
        "example_id": tf.FixedLenFeature([], tf.string),
        "x": tf.FixedLenFeature([261], tf.float32),
        "x1": tf.FixedLenFeature([261], tf.float32),
    }
    record_batch = tf.placeholder(dtype=tf.string, name='examples')
    features = tf.parse_example(record_batch, features=feature_map)
    return tf.estimator.export.ServingInputReceiver(features,
                                                    {'examples': record_batch})


def model_fn(model, features, labels, mode):
    x = tf.concat([features['x'], features['x1']], axis=1)

    w1f = tf.get_variable('w1f',
                          shape=[261 * 2, 128],
                          dtype=tf.float32,
                          initializer=tf.random_uniform_initializer(
                              -0.01, 0.01))
    b1f = tf.get_variable('b1f',
                          shape=[128],
                          dtype=tf.float32,
                          initializer=tf.zeros_initializer())

    act1_f = tf.nn.relu(tf.nn.bias_add(tf.matmul(x, w1f), b1f))

    if mode == tf.estimator.ModeKeys.TRAIN:
        gact1_f = model.send('act1_f', act1_f, require_grad=True)
        optimizer = tf.train.GradientDescentOptimizer(0.1)
        train_op = model.minimize(
            optimizer,
            act1_f,
            grad_loss=gact1_f,
            global_step=tf.train.get_or_create_global_step())
        logging.info("trainning")
        return model.make_spec(mode,
                               loss=tf.math.reduce_mean(act1_f),
                               train_op=train_op)

    logging.info("eval")
    if mode == tf.estimator.ModeKeys.EVAL:
        model.send('act1_f', act1_f, require_grad=False)
        fake_loss = tf.reduce_mean(act1_f)
        return model.make_spec(mode=mode, loss=fake_loss)

    # mode == tf.estimator.ModeKeys.PREDICT:
    return model.make_spec(mode=mode, predictions={'act1_f': act1_f})


def main(args):
    logging.basicConfig(level=logging.INFO)
    flt.trainer_worker.train(
        'leader', args, input_fn,
        model_fn, serving_input_receiver_fn)


if __name__ == '__main__':
    parser = flt.trainer_worker.create_argument_parser()
    args = parser.parse_args()
    main(args)
