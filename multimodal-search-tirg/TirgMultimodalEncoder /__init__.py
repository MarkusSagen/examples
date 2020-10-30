__copyright__ = "Copyright (c) 2020 Jina AI Limited. All rights reserved."
__license__ = "Apache-2.0"

import os
import sys
import numpy as np
import pickle
from typing import List

from jina.executors.decorators import batching, as_ndarray
from jina.executors.encoders.multimodal import BaseMultiModalEncoder
from jina.excepts import PretrainedModelFileDoesNotExist
from jina.executors.devices import TorchDevice

# sys.path.append(".")
from img_text_composition_models import TIRG

class TirgMultiModalEncoder(TorchDevice, BaseMultiModalEncoder):

    def __init__(self, model_path: str,
                 texts_path: str,
                 positional_modality: List[str] = ['visual', 'textual'],
                 channel_axis: int = -1, 
                 *args, **kwargs):
        """
        :param model_path: the path where the model is stored.
        """
        super().__init__(*args, **kwargs)
        self.model_path = model_path
        self.texts_path = texts_path
        self.positional_modality = positional_modality
        self.channel_axis = channel_axis
        # axis 0 is the batch
        self._default_channel_axis = 1

    def post_init(self):
        super().post_init()
        import torch
        if self.model_path and os.path.exists(self.model_path):
            with open (self.texts_path, 'rb') as fp:
                texts = pickle.load(fp)
            self.model = TIRG(texts, 512)
            model_sd = torch.load(self.model_path, map_location=torch.device('cpu'))
            self.model.load_state_dict(model_sd['model_state_dict'])
            self.model.eval()
            self.to_device(self.model)
        else:
            raise PretrainedModelFileDoesNotExist(f'model {self.model_path} does not exist')

    def _get_features(self, data):
        visual_data = data[(self.positional_modality.index('visual'))]
        if self.channel_axis != self._default_channel_axis:
            visual_data = np.moveaxis(visual_data, self.channel_axis, self._default_channel_axis)
        textual_data = data[(self.positional_modality.index('textual'))]
        
        visual_data = torch.from_numpy(visual_data.astype('float32'))
        textual_data = torch.from_numpy(textual_data.astype('float32'))
        
        if self.on_gpu:
            visual_data = visual_data.cuda()
            textual_data = textual_data.cuda()
            
        img_features = self.model.extract_img_feature(visual_data)
        text_features = self.model.extract_text_feature(textual_data)
        
        return self.model.compose_img_text_features(img_features, text_feature)

    @batching
    @as_ndarray
    def encode(self, *data: 'np.ndarray', args, **kwargs) -> 'np.ndarray':
        import torch
        _feature = self._get_features(data).detach()
        if self.on_gpu:
            _feature = _feature.cpu()
        _feature = _feature.numpy()
        return _feature