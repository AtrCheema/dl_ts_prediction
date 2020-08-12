from run_model import make_model
from main import Model
from models.global_variables import keras, tf
import pandas as pd


class CustomModel(Model):

    def build_nn(self):

        inputs = keras.layers.Input(shape=(self.lookback, self.ins))

        lstm_activations = self.add_LSTM(inputs, self.nn_config['lstm_config'])

        predictions = keras.layers.Dense(self.outs, activation=tf.nn.elu)(lstm_activations)

        self.k_model = self.compile(inputs, predictions)

        return

    def train_nn(self, st=0, en=None, indices=None, **callbacks):
        # Instantiate an optimizer.
        optimizer = keras.optimizers.Adam(learning_rate=self.nn_config['lr'])
        # Instantiate a loss function.
        loss_fn = self.loss

        # Prepare the training dataset.
        batch_size = self.data_config['batch_size']

        indices = self.get_indices(indices)

        train_x, train_y, train_label = self.fetch_data(start=st, ende=en, shuffle=True,
                                                        cache_data=self.data_config['CACHEDATA'],
                                                        indices=indices)

        train_dataset = tf.data.Dataset.from_tensor_slices((train_x, train_label))
        train_dataset = train_dataset.shuffle(buffer_size=1024).batch(batch_size)


        for epoch in range(self.nn_config['epochs']):
            print("\nStart of epoch %d" % (epoch,))

            # Iterate over the batches of the dataset.
            for step, (x_batch_train, full_outputs) in enumerate(train_dataset):

                # Open a GradientTape to record the operations run
                # during the forward pass, which enables autodifferentiation.
                with tf.GradientTape() as tape:

                    # Run the forward pass of the layer.
                    # The operations that the layer applies
                    # to its inputs are going to be recorded
                    # on the GradientTape.
                    mask = tf.greater(tf.reshape(full_outputs, (-1,)), 0.0)  # (batch_size,)
                    y_obj = full_outputs[mask]  # (vals_present, 1)
                    logits = self.k_model(x_batch_train, training=True)  # Logits for this minibatch

                    logits_obj = logits[mask]
                    # Compute the loss value for this minibatch.
                    loss_value = keras.backend.mean(loss_fn(y_obj, logits_obj))

                # Use the gradient tape to automatically retrieve
                # the gradients of the trainable variables with respect to the loss.
                grads = tape.gradient(loss_value, self.k_model.trainable_weights)

                # Run one step of gradient descent by updating
                # the value of the variables to minimize the loss.
                optimizer.apply_gradients(zip(grads, self.k_model.trainable_weights))

                # Log every 200 batches.
                if step % 20 == 0:
                    print(
                        "Training loss (for one batch) at step %d: %.4f"
                        % (step, float(loss_value))
                    )
                    print("Seen so far: %s samples" % ((step + 1) * 64))
        return loss_value


data_config, nn_config, total_intervals = make_model(lstm_units=64,
                             dropout=0.4,
                             rec_dropout=0.5,
                             lstm_act='relu',
                             batch_size=32,
                             lookback=15,
                             lr=8.95e-5,
                             ignore_nans=True,
                                                     epochs=20)

df = pd.read_csv('data/all_data_30min.csv')

model = CustomModel(data_config=data_config,
                  nn_config=nn_config,
                  data=df,
                  # intervals=total_intervals
                  )

model.build_nn()

history = model.train_nn(indices='random', tensorboard=True)

# y, obs = model.predict()
