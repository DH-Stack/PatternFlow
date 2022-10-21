"""
Author: Remington Greenhill-Brown
SN: 44343309
"""
from dataset import *
from modules import *  
import tensorflow as tf
from tensorflow.keras.optimizers import Adam
import matplotlib.pyplot as plt
import numpy as np
import os
from sklearn.manifold import TSNE

"""
ModelTrainer: class to house model training functions
"""
class ModelTrainer:
    """
    __init__(checkpointPath): initialises data pulled from dataset class and other variables for model training.
    params: checkpointPath - place where model checkpoints/weights should be saved to for later recall.
    """
    def __init__(self, checkpointPath):
        self.optimizer = Adam(learning_rate=0.001)
        self.dataset = DataProcess()

        (self.features, 
        self.labels, 
        self.adjacency,  
        self.trainMask, 
        self.validaMask, 
        self.testMask, 
        self.trainLabels, 
        self.validaLabels, 
        self.testLabels, 
        self.target, 
        self.numNodes, 
        self.numFeatures) = self.dataset.getData()

        self.classes = len(np.unique(self.target))

        self.model = GCN(self.numNodes, self.numFeatures, self.classes)
        self.validation_data = ([self.features, self.adjacency], self.labels, self.validaMask)

        # set checkpoint directory based on input checkpoint path
        self.checkpointDir = os.path.dirname(checkpointPath)
        #create checkpoint callback
        self.cp_callback = tf.keras.callbacks.ModelCheckpoint(checkpointPath, save_weights_only=True, verbose=1, save_freq=10)

        # number of epochs to run model for
        self.epochs = 350

        self.trainAcc = []
        self.trainLoss = []
        self.valAcc = []
        self.valLoss = []

    """
    generateModel(): takes model created in modules.py, compiles it, and fits it using keras. saves checkpoints of the weights for later recall
    returns: compiled and fitted model
    """
    def generateModel(self):
        self.model.compile(optimizer=self.optimizer, loss='categorical_crossentropy', weighted_metrics=['acc'])
        self.model.fit(
            [self.features, self.adjacency],
            self.labels,
            sample_weight=self.trainMask,
            epochs=self.epochs,
            batch_size=self.numNodes,
            validation_data=self.validation_data,
            shuffle=False,
            callbacks=[self.cp_callback]
        )
        return self.model

    """
    getSummary(): gets the model summary created by keras
    returns: a summary of the model
    """
    def getSummary(self):
        self.model.summary()

    """
    lossPlots(): generates loss plots of model training. 
    output: plot of training and validation accuracy, plot of training and validation loss
    """
    def lossPlots(self):
        epochRange = list(range(1,self.epochs+1))
        
        plt.plot(epochRange, self.trainAcc, 'r', label='Training Accuracy')
        plt.plot(epochRange, self.valAcc, 'g', label='Validation Accuracy')
        plt.title('Training and validation accuracy')
        plt.legend()

        plt.figure()

        plt.plot(epochRange, self.trainLoss, 'r', label='Training Loss')
        plt.plot(epochRange, self.valLoss, 'g', label='Validation Loss')
        plt.title('Training and Validation Loss')
        plt.legend()
        plt.show()

    """
    predictResults(): generates predictions from the test set of data using keras's model prediction
    returns: classifications of the test set data using the trained model
    """
    def predictResults(self):
        return self.model.predict([self.features, self.adjacency], batch_size=self.numNodes), self.labels[self.testMask]
    
    """
    plotTSNE(labels, predictions): creates tsne plot given labels and predictions
    params: labels, predictions - labels/classes of the data; predictions generated by the predictResults function
    outputs: tsne plot of inputted data
    """
    def plotTSNE(self, labels, predictions):
        tsne = TSNE(n_components=2).fit_transform(predictions)
        colourMap = np.argmax(labels, axis=1)
        plt.figure(figsize=(15,15))
        for classes in range(self.classes):
            indices = np.where(colourMap == classes)
            indices = indices[0]
            plt.scatter(tsne[indices, 0], tsne[indices, 1], label=classes)

        plt.legend()
        plt.show()

def main():
 model = ModelTrainer("facebook.npz", "training/cp.ckpt")
 model.generateModel()
 model.getSummary()
 model.lossPlots()
 prediction, testLabs = model.predictResults()
 model.plotTSNE(testLabs, prediction)
 

if __name__ == '__main__':
    main()




