import numpy as np

from .sort.nn_matching import NearestNeighborDistanceMetric
from .sort.detection import Detection
from .sort.tracker import Tracker
import importlib
import os
import pickle

__all__ = ['DeepSort']


class DeepSort(object):

    def __init__(self, cfg, max_dist=0.2):

        self.cfg = cfg
        feat_extractor_module = importlib.import_module(cfg.feature_extractor.module_name)


        if cfg.feature_extractor.feature_extractor_name == "abd_net_extractor":
            self.feature_extractor = getattr(feat_extractor_module,cfg.feature_extractor.class_name)(cfg.feature_extractor.abd_net_extractor)
        else:
            self.feature_extractor = getattr(feat_extractor_module, cfg.feature_extractor.class_name)(cfg.feature_extractor)

        max_cosine_distance = max_dist

        nn_budget = cfg.tracker.nn_budget
        metric = NearestNeighborDistanceMetric("cosine", max_cosine_distance, nn_budget)
        self.tracker = Tracker(metric)

    def update(self, bboxes_xtylwh, confidences, dataset_img):
        '''
        Attention the input bounding boxes have to be in the x-top y-left and width height format!
         Not the x-center y-center width
        :param bboxes_xtylwh: input bounding boxes have to be in the x-top y-left and width height format
        :param confidences:
        :param ori_img:
        :return:
        '''
        self.height, self.width = dataset_img.img.shape[:2]
        # generate detections

        feature_config_path = os.path.join(self.cfg.feature_extractor.features_path, self.cfg.general.config_basename)
        os.makedirs(feature_config_path,exist_ok=True)
        feature_pkl_path = os.path.join(feature_config_path, dataset_img.image_name_no_ext + ".pkl")


        if os.path.exists(feature_pkl_path):
            with open(feature_pkl_path, 'rb') as handle:
                detections = pickle.load(handle)

        else:

            features = self._get_features(bboxes_xtylwh, dataset_img.img)
            detections = [Detection(bbox_xtylwh, conf, feature) for bbox_xtylwh,conf, feature in zip(bboxes_xtylwh, confidences, features)]
            with open(feature_pkl_path, 'wb') as handle:
                pickle.dump(detections, handle, protocol=pickle.HIGHEST_PROTOCOL)



        # update tracker
        self.tracker.predict()
        self.tracker.update(detections)

        # output bbox identities
        outputs = []
        for track in self.tracker.tracks:
            if not track.is_confirmed() or track.time_since_update > 1:
                continue
            x,y,w,h = track.to_tlwh()
            track_id = track.track_id
            outputs.append(np.array([x,y,w,h,track_id,track.last_detection_idx()], dtype=np.int))
        if len(outputs) > 0:
            outputs = np.stack(outputs,axis=0)
        return outputs



    
    def _get_features(self, bboxes_xtylwh, ori_img):
        im_crops = []
        for bbox in bboxes_xtylwh:
            x,y,w,h = bbox
            im = ori_img[y:y+h, x:x+w]
            im_crops.append(im)
        if im_crops:
            features = self.feature_extractor.extract(im_crops)
        else:
            features = np.array([])
        return features

