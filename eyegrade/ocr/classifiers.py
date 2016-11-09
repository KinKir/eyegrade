# Eyegrade: grading multiple choice questions with a webcam
# Copyright (C) 2015 Rodrigo Arguello, Jesus Arias Fisteus
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
import json
import os.path

import cv2
import numpy as np

from . import preprocessing
from . import deepclassifier
from .. import utils


DEFAULT_DIG_CLASS_FILE = 'digit_classifier.json.gz'
DEFAULT_DIG_META_FILE = 'digit_classifier_meta.txt'
DEFAULT_CROSS_CLASS_FILE = 'cross_classifier.dat.gz'
DEFAULT_CROSS_META_FILE = 'cross_classifier_metadata.json'
DEFAULT_DIR = 'classifiers'


def create_digit_classifier():
    classifier_file = _resource(DEFAULT_DIG_CLASS_FILE)
    meta_file = _resource(DEFAULT_DIG_META_FILE)
    classifier = deepclassifier.Classifier(load_from_file=classifier_file,
                                           mini_batch_size=1)
    return DigitClassifierWrapper(classifier, meta_file)


class SVMClassifier(object):
    def __init__(self, num_classes, features_extractor, load_from_file=None):
        self.num_classes = num_classes
        self.features_extractor = features_extractor
        self.svm = cv2.SVM()
        if load_from_file:
            self.svm.load(_resource(load_from_file))

    @property
    def features_len(self):
        return self.features_extractor.features_len

    def train(self, samples, params=None):
        features = np.ndarray(shape=(len(samples), self.features_len),
                              dtype='float32')
        labels = np.ndarray(shape=(len(samples), 1), dtype='float32')
        for i, sample in enumerate(samples):
            features[i,:] = self.features_extractor.extract(sample)
            labels[i] = float(sample.label)
        svm_params = dict(kernel_type=cv2.SVM_RBF,
                          svm_type=cv2.SVM_C_SVC,
                          C=10,
                          gamma=0.01)
        if params:
            if 'C' in params:
                svm_params['C'] = params['C']
            if 'gamma' in params:
                svm_params['gamma'] = params['gamma']
        self.svm.train(features, labels, params=svm_params)

    def classify(self, sample):
        features = self.features_extractor.extract(sample)
        return int(round(self.svm.predict(features)))

    def reset(self):
        self.svm = cv2.SVM()

    def save(self, filename):
        self.svm.save(filename)


class DigitClassifierWrapper(object):
    def __init__(self, classifier, confusion_matrix_file):
        self.classifier = classifier
        self.confusion_matrix = \
            self._load_confusion_matrix(confusion_matrix_file)

    def classify_digit(self, sample):
        digit = self.classify(sample)
        weights = self.confusion_matrix[:, digit]
        return (digit, weights)

    @staticmethod
    def _load_confusion_matrix(filename):
        if filename:
            with open(_resource(filename)) as f:
                metadata = json.load(f)
                matrix = np.array(metadata['confusion_matrix'], dtype=float)
        else:
            matrix = np.diag(np.ones(10, dtype=float))
        return matrix


class SVMCrossesClassifier(SVMClassifier):
    def __init__(self, features_extractor, load_from_file=None):
        super(SVMCrossesClassifier, self).__init__(2, features_extractor,
                                                load_from_file=load_from_file)

    def is_cross(self, sample):
        return self.classify(sample) == 1


class DefaultCrossesClassifier(SVMCrossesClassifier):
    def __init__(self, load_from_file=DEFAULT_CROSS_CLASS_FILE):
        super(DefaultCrossesClassifier, self).__init__( \
                        preprocessing.CrossesFeatureExtractor(),
                        load_from_file=load_from_file)

    def train(self, samples, params=None):
        super(DefaultCrossesClassifier, self).train( \
                                              samples,
                                              dict(C=100, gamma=0.01))

def _resource(filename):
    return utils.resource_path(os.path.join(DEFAULT_DIR, filename))
