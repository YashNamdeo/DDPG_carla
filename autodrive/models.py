

from keras.layers import TimeDistributed, Conv2D, LSTM, Input, BatchNormalization, Flatten, Dense, Concatenate, GRU, AveragePooling2D
from keras.initializers import RandomUniform
from keras.models import Model
from keras.utils import plot_model
from keras.regularizers import l2


class Models(object):

    def __init__(self, image_shape=None, odometry_shape=None, window_length=None, nb_actions=None):
        self.window_length = window_length
        self.odometry_shape = odometry_shape
        self.image_shape = image_shape
        self.nb_actions = nb_actions

        self.ih_img, self.ih_odo, self.ih_out = self._build_inputhead()
        self.actor = None
        self.critic = None

    def _build_inputhead(self):

        layer_prefix = "ih"
        img_ip = Input(shape=(self.window_length,) +
                       self.image_shape, name="{}_image_in".format(layer_prefix))
        odo_ip = Input(shape=(self.window_length,) +
                       self.odometry_shape, name="{}_odometry_in".format(layer_prefix))

        x = TimeDistributed(Conv2D(filters=16, kernel_size=(
            5, 5), padding="same", strides=3, activation="relu"))(img_ip)
        x = TimeDistributed(Conv2D(filters=32, kernel_size=(
            3, 3), padding="same", strides=2, activation="relu"))(x)
        x = TimeDistributed(Conv2D(filters=32, kernel_size=(
            3, 3), padding="same", strides=2, activation="relu"))(x)
        x = TimeDistributed(AveragePooling2D(pool_size=2))(x)
        x = TimeDistributed(BatchNormalization())(x)
        x = TimeDistributed(Flatten())(x)
        # x = LSTM(200, recurrent_dropout=0.2, dropout=0.2)(x)
        x = GRU(256, recurrent_dropout=0.2, dropout=0.2)(x)

        y = TimeDistributed(Dense(32, activation="relu"))(odo_ip)
        y = TimeDistributed(BatchNormalization())(y)
        # y = LSTM(16, recurrent_dropout=0.2, dropout=0.2)(y)
        y = GRU(16, recurrent_dropout=0.2, dropout=0.2)(y)

        op = Concatenate()([x, y])
        op = BatchNormalization(name="{}_out".format(layer_prefix))(op)

        return img_ip, odo_ip, op

    def build_actor(self):

        layer_prefix = "actor"

        x = Dense(200, activation="relu", name="{}_dense_1".format(
            layer_prefix))(self.ih_out)
        x = Dense(200, activation="relu",
                  name="{}_dense_2".format(layer_prefix))(x)
        out = Dense(self.nb_actions, activation="tanh",
                    kernel_initializer=RandomUniform(minval=-3e-4, maxval=3e-4), name="{}_out".format(layer_prefix))(x)

        self.actor = Model(
            inputs=[self.ih_odo, self.ih_img], outputs=out, name="actor")
        print(self.actor.summary())
        # plot_model(self.actor, to_file="imgs/actor.png", show_shapes=True)

        return self.actor

    def build_critic(self):

        layer_prefix = "critic"

        self.action_input = action_input = Input(shape=(self.nb_actions,),
                                                 name="{}_action_inp".format(layer_prefix))
        x = Concatenate(name="{}_inp".format(layer_prefix))(
            [self.ih_out, action_input])
        x = BatchNormalization()(x)
        x = Dense(200, activation="relu", name="{}_dense_1".format(
            layer_prefix))(x)
        x = Dense(200, activation="relu",
                  name="{}_dense_2".format(layer_prefix))(x)
        out = Dense(1, activation="linear", kernel_initializer=RandomUniform(
            minval=-3e-4, maxval=3e-4), name="{}_out".format(layer_prefix), kernel_regularizer=l2(l=0.01))(x)

        self.critic = Model(
            inputs=[self.ih_odo, self.ih_img, action_input], outputs=out, name="critic")
        print(self.critic.summary())
        # plot_model(self.critic, to_file="imgs/critic.png", show_shapes=True)

        return self.critic


def main():
    models = Models(image_shape=(84, 84, 3), odometry_shape=(
        4,), window_length=4, nb_actions=2)
    actor = models.build_actor()
    critic = models.build_critic()

    model = Model(inputs=[models.ih_odo, models.ih_img, models.action_input],
                  outputs=actor.outputs + critic.outputs)
    # plot_model(model, to_file="imgs/model.png", show_shapes=True)
    print(model.summary())


if __name__ == "__main__":
    main()
