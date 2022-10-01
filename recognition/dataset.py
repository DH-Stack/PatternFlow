import torch
import os
from PIL import Image
import torchvision.transforms as transform
import torch.nn.functional as F

class Dataset(torch.utils.data.Dataset):
    def __init__(self, path, img_size=255):
        """
        Image loader base class
        
        Takes a path to folder of images.
        All images are resized to [im_len, im_len] when an item is requested.
        """
        self.path = path
        self.files = os.listdir(self.path)
        self.len = len(self.files)
        self.img_size = img_size
        self.trf = transform.ToTensor()

    def __len__(self):
        return self.len
    
    def __getitem__(self, index):
        image = Image.open(self.path + self.files[index])
        image = image.resize((self.img_size, self.img_size))
        return self.trf(image)  * 2 - 1
