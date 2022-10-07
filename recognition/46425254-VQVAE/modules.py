import torch
import torch.nn as nn
import torch.utils as utils
import torchvision
import numpy as np


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#Setting Global Parameters
image_dim = (3,256,256)
learning_rate = 0.0001
latent_space = 256
commitment_loss = 0.25

class Encoder(nn.Module):
    
    def __init__(self):
        super(Encoder, self).__init__()
        
        #3 convolutional layers for a latent space of 64
        self.model = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=4, stride = 2, padding = 1),
            # 3 * 256 * 256 -> 64 * 128 * 128
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.1),
            
            nn.Conv2d(64, 128, kernel_size=4, stride = 2, padding = 1),
            # 64 * 128 * 128 -> 128 * 64 * 64
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.1),
            
            nn.Conv2d(128, latent_space, kernel_size=4, stride = 2, padding = 1),
            # 64 * 128 * 128 -> 256 * 64 * 64
            
            nn.Sigmoid(),)
        
    
    def forward(self, x):
        return self.model(x)
            
            

    
    
class Decoder(nn.Module):
    
    def __init__(self):
        super(Decoder, self).__init__()
        
        self.model = nn.Sequential(
            nn.ConvTranspose2d(latent_space, 128, kernel_size=4, stride = 2, padding = 1),
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.1),
            
            nn.ConvTranspose2d(128, 64, kernel_size= 4, stride = 2, padding = 1),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.1),
            
            nn.ConvTranspose2d(64, 3, kernel_size = 4, stride = 2, padding = 1),
            nn.Tanh(),
            )
        
        
    def forward(self, x):
        return self.model(x)
    
"""
Since the dimension of e is not defined, it can grow arbitrarily if the 
encoder outputs are trained faster than the embedded vector. A commitment
loss is therefore needed to regulate the encoder outputs to commit to an
embedding as a Hyperparameter.



"""
class VQ(nn.Module):

    """
    Define a latent embedding space e, which is a real number space with 
    relation K * D, where:
        K is the size of the discrete latent space
        D is the size of the vectors embedded into the space
    
    There are K embedded vectors of dimensionality D
        
    e is the lookup table for the encoded output, and based on the output of
    encoder, chooses the closest embedded vector as input for the decoder.
    
    
    
    Parameters:
        self.num_embeddings -> Parameter K
        self.embedding_dim -> Parameter D
        self.commitment_loss -> the loss value that calculates
    """    
    
    def __init__(self, num_embeddings, embedding_dim, commitment_loss):
        super(VQ, self).__init__()
    
        self.num_embeddings = num_embeddings
        self.embedding_dim = embedding_dim
        
        
        self.embedding_table = nn.Embedding(
            self.num_embeddings, self.embedding_dim)
        
        #initialise the weights of the vectors in the embedding table
        #weights are uniform relative to the number of embedded vectors
        self.embedding_table.weight.data.uniform_(-1/self.num_embeddings,
                                                  1/self.num_embeddings)
        
        self.commitment_loss = commitment_loss
    
    
    """
    Quantizes the encoder output.
    
    Parameters:
        encoder_inputs -> the output tensor from encoding
        
    Returns:
        quantized -> the quantized tensor
        loss -> loss of information after quantizing
    """
    def forward(self, encoder_inputs):
        #currently the encoder_inputs are in Batch Channel Height Width Format
        #Channel needs to be moved to so that the input can be quantised
        
        encoder_inputs = encoder_inputs.permute(0, 2, 3, 1)
        #reformat memory layout since it is has been transformed
        encoder_inputs = encoder_inputs.contiguous() 
        shape = encoder_inputs.shape
        
        #flatten the Batch Height and Width into such that the tensor becomes
        #(N = B*H*W, Channel)
        
        flattened_inputs = encoder_inputs.view(-1, self.embedding_dim)
        
        """
        calculate distances between each of the flattened inputs and the
        weights of the of embedded table vectors, creates N*K distances, where 
        N is B*H*W and K the num_embeddings
        """
        
        all_distances = (torch.sum(flattened_inputs**2, dim=1, keepdim = True)
                         + torch.sum(self.embedding_table.weight**2, dim=1)
                         - 2 * torch.matmul(flattened_inputs, 
                                            self.embedding_table.weight.t()))
        
        # find the smallest distance from N*K distance combinations
        # get the index tensor of the smallest distance
        indexes = torch.argmin(all_distances, dim=1).unsqueeze(1)
        
        # create a zeros tensor, with the position at indexes being 1
        # This creates a "beacon" so that position can be replaced by a 
        # embedded vector.
        encodings = torch.zeros(indexes.shape[0], self.num_embeddings, 
                                device = device)
        
        encodings.scatter_(1, indexes, 1)
        
        # Quantize and reshape to BHWC format
        
        quantized_bhwc = torch.matmul(encodings, 
                                      self.embedding_table.weight).view(shape)
        
        """
        the loss function is used from equation 3 of the VQVAE paper provided 
        in the references in readme.The first term of the loss fucntion, the 
        reconstruction loss, is calculated later.
        
        The stop gradients used can be applied using the detach() function, 
        which removes it from the current graph and turns it into a constant.
        
        """
        first_term = nn.functional.mse_loss(quantized_bhwc.detach(), 
                                            encoder_inputs)
        
        second_term = nn.functional.mse_loss(quantized_bhwc, 
                                             encoder_inputs.detach())
        
        beta = self.commitment_loss
        
        
        loss = first_term + beta * second_term
        
        # backpropagate and update gradients back at to the encoder using the 
        # quantized gradients
        
        quantized_bhwc = encoder_inputs + (quantized_bhwc - 
                                           encoder_inputs).detach()
        
        # restructure the VQ output to be Batch Channel Height Width format
        quantized = quantized_bhwc.permute(0, 3, 1, 2)
        # reformat memory, just like when it was transformed to bchw format
        quantized = quantized.contiguous()
        
        return quantized, loss
        
"""
Model that compiles the encoder, Vector Quantizer and decoder together.
Some extra scaffolding added for tensor dimension compatability
"""
class VQVAE(nn.Module):
        
    def __init__(self):
        super(VQVAE, self).__init__()
        
        self.encoder = Encoder()
        self.VQ = VQ(512, 256, commitment_loss)
        self.decoder = Decoder()
        
    def forward(self, inputs):
        outputs = self.encoder(inputs)
        quantized_outputs, loss = self.VQ(outputs)
        #print(quantized_outputs.shape)
        decoder_outputs = self.decoder(quantized_outputs)
        
        return decoder_outputs, loss
        

    def get_decoder(self):
        return self.decoder
    
    def get_encoder(self):
        return self.encoder
        

"""
Abstract for creating a masked convolution for PixelCNN. Based on PixelCNN
paper in the reference

Parameters:
    size -> size of the grid
    current_pos -> the current position the pointer is in
    mask_type -> the type the mask will be
    
Returns:
    mask_grid -> numpy grid that has "1" x1 to xi (current pos), else "0"
    

"""
def conv_mask_abstract( size, current_pos, mask_type):
    
    mask_grid = np.zeros((size, size))
    
    x, y = current_pos
    for i in range(size):
        for j in range(size):
            if j < x or i < y:
                mask_grid[i][j] = 1

    if mask_type == "B":
        mask_grid[y][x] = 1
    else:
        mask_grid[y][x] = 0
        
    return mask_grid
    
                
class MaskedConv2d(nn.Conv2d):
    
    def __init__(self, mask_type, *args, **kwargs):
        #Inherits 2d convolutional layer and its parameters
        super(MaskedConv2d, self).__init__(*args, **kwargs)
        
        b, c, h, w  = self.weight.shape()
        centre_h, centre_w = h//2, w//2
        #setup the mask
        self.mask = conv_mask_abstract(h, (centre_w, centre_h), mask_type)
        
        #register the mask
        self.register_buffer('mask', torch.from_numpy(self.mask).float())
        
    def forward(self, x):
        #apply mask
        self.weight.data = self.weight.data * self.mask
        #use the forward from nn.Conv2d
        return  super(MaskedConv2d, self).forward(x)
        
        
#class PixelCNN(nn.Module):
    
        
        
        
        
        
        
        
    