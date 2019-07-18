import tensorflow as tf
import data_prepare
from tensorflow.contrib import learn
import numpy as np
from abcnn import abcnn_mdoel
import config as config
from tqdm import tqdm
from sklearn.metrics import f1_score
from sklearn import metrics
import os

con = config.Config()
parent_path = os.path.dirname(os.getcwd())
data_pre = data_prepare.Data_Prepare()


class TrainModel(object):
    '''
        训练模型
        保存模型
    '''
    def pre_processing(self):
        train_texta, train_textb, train_tag = data_pre.readfile(parent_path+'/data/train.txt')
        data = []
        data.extend(train_texta)
        data.extend(train_textb)
        data_pre.build_vocab(data, parent_path+'/save_model' + '/abcnn/vocab.pickle')
        # 加载词典
        self.vocab_processor = learn.preprocessing.VocabularyProcessor.restore(parent_path+'/save_model/abcnn' +
                                                                               '/vocab.pickle')
        train_texta_embedding = np.array(list(self.vocab_processor.transform(train_texta)))
        train_textb_embedding = np.array(list(self.vocab_processor.transform(train_textb)))

        dev_texta, dev_textb, dev_tag = data_pre.readfile(parent_path+'/data/dev.txt')
        dev_texta_embedding = np.array(list(self.vocab_processor.transform(dev_texta)))
        dev_textb_embedding = np.array(list(self.vocab_processor.transform(dev_textb)))
        return train_texta_embedding[:1000], train_textb_embedding[:1000], np.array(train_tag)[:1000], \
               dev_texta_embedding[:1000], dev_textb_embedding[:1000], np.array(dev_tag)[:1000]

    def get_batches(self, texta, textb, tag):
        num_batch = int(len(texta) / con.Batch_Size)
        for i in range(num_batch):
            a = texta[i*con.Batch_Size:(i+1)*con.Batch_Size]
            b = textb[i*con.Batch_Size:(i+1)*con.Batch_Size]
            t = tag[i*con.Batch_Size:(i+1)*con.Batch_Size]
            yield a, b, t

    def trainModel(self):
        train_texta_embedding, train_textb_embedding, train_tag, \
        dev_texta_embedding, dev_textb_embedding, dev_tag = self.pre_processing()
        # 定义训练用的循环神经网络模型
        with tf.variable_scope('model', reuse=None):
            # abcnn
            DEFAULT_CONFIG = [{'type': 'ABCNN-1', 'w': 3, 'n': 50, 'nl': 'tanh'} for _ in range(3)]
            model = abcnn_mdoel.ABCNN(True, learning_rate=con.learning_rate, conv_layers=3, embed_size=con.embedding_size,
                                      vocabulary_size=len(self.vocab_processor.vocabulary_),
                                      sentence_len=len(train_texta_embedding[0]), config=DEFAULT_CONFIG)

        # 训练模型
        session_conf = tf.ConfigProto(allow_soft_placement=True, log_device_placement=False)
        sess = tf.Session(config=session_conf)
        with sess.as_default():
            tf.global_variables_initializer().run()
            saver = tf.train.Saver()
            best_f1 = 0.0
            for time in range(con.epoch):
                print("training " + str(time + 1) + ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                model.is_trainning = True
                loss_all = []
                accuracy_all = []
                for texta, textb, tag in tqdm(
                        self.get_batches(train_texta_embedding, train_textb_embedding, train_tag)):
                    feed_dict = {
                        model.text_a: texta,
                        model.text_b: textb,
                        model.y: tag,
                        model.dropout_keep_prob: con.dropout_keep_prob
                    }
                    _, cost, accuracy = sess.run([model.train_op, model.loss, model.accuracy], feed_dict)
                    loss_all.append(cost)
                    accuracy_all.append(accuracy)

                print("第" + str((time + 1)) + "次迭代的损失为：" + str(np.mean(np.array(loss_all))) + ";准确率为：" +
                      str(np.mean(np.array(accuracy_all))))

                def dev_step():
                    """
                    Evaluates model on a dev set
                    """
                    loss_all = []
                    accuracy_all = []
                    predictions = []
                    for texta, textb, tag in tqdm(
                            self.get_batches(dev_texta_embedding, dev_textb_embedding, dev_tag)):
                        feed_dict = {
                            model.text_a: texta,
                            model.text_b: textb,
                            model.y: tag,
                            model.dropout_keep_prob: 1.0
                        }
                        dev_cost, dev_accuracy, prediction = sess.run([model.loss, model.accuracy,
                                                                       model.prediction], feed_dict)
                        loss_all.append(dev_cost)
                        accuracy_all.append(dev_accuracy)
                        predictions.extend(prediction)
                    y_true = [np.nonzero(x)[0][0] for x in dev_tag]
                    y_true = y_true[0:len(loss_all)*con.Batch_Size]
                    f1 = f1_score(np.array(y_true), np.array(predictions), average='weighted')
                    print('分类报告:\n', metrics.classification_report(np.array(y_true), predictions))
                    print("验证集：loss {:g}, acc {:g}, f1 {:g}\n".format(np.mean(np.array(loss_all)),
                                                                      np.mean(np.array(accuracy_all)), f1))
                    return f1

                model.is_trainning = False
                f1 = dev_step()

                if f1 > best_f1:
                    best_f1 = f1
                    saver.save(sess, parent_path + "/save_model/abcnn/model.ckpt")
                    print("Saved model success\n")


if __name__ == '__main__':
    train = TrainModel()
    train.trainModel()
