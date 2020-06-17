
import numpy as np
import traceback as tb
import pickle
import time

import os
os.environ["CUDA_VISIBLE_DEVICES"] = '-1' 

from keras.models import Sequential, Model
from keras.layers import Dense, Activation, Flatten, Input, Concatenate
from keras.optimizers import Adam
from keras.callbacks import TensorBoard
import keras.backend as K

from rl.random import OrnsteinUhlenbeckProcess
from rl.callbacks import ModelIntervalCheckpoint, FileLogger

from carla_rl import carla_config
from carla_rl.carla_environment_wrapper import CarlaEnvironmentWrapper as CarlaEnv
from carla_settings import get_carla_settings

from processor import MultiInputProcessor
from models import Models
from memory import PrioritizedExperience
from agent import DDPG_PERAgent

ENV_NAME = "Carla"
np.random.seed(123)

EXP_NAME = str(time.time())

config_file = "mysettings.ini"  # file should be placed in CARLA_ROOT folder
checkpoint_weights_filename = 'checkpoints/ddpg_' + \
    ENV_NAME + '_weights_{step}.h5f'
log_filename = 'ddpg_{}_log.json'.format(ENV_NAME)
tb_logs = "logs/{}".format(EXP_NAME)

nb_actions = 2
window_size = 4
odometry_shape = (10,)

# memory params
alpha0 = 0.6
beta0 = 0.6

nb_steps = 10**6

train_history = None

while True:
    env = CarlaEnv(is_render_enabled=False, automatic_render=False, num_speedup_steps=1, run_offscreen=False,
                   cameras=["SceneFinal"], save_screens=False, carla_settings=get_carla_settings(), carla_server_settings=config_file, early_termination_enabled=True)

    K.clear_session()

    models = Models(image_shape=(carla_config.render_width, carla_config.render_height, 3),
                    odometry_shape=odometry_shape, window_length=window_size, nb_actions=nb_actions)

    actor = models.build_actor()
    critic = models.build_critic()

    callbacks = []
    callbacks = [ModelIntervalCheckpoint(
        checkpoint_weights_filename, interval=2500)]
    callbacks += [FileLogger(log_filename, interval=100)]
    callbacks += [TensorBoard(log_dir=tb_logs)]

    try:
        processor = MultiInputProcessor(window_length=window_size, nb_inputs=2)

        try:
            print("Trying to load 'memory'", end="")
            memory = pickle.load(open("memory.pkl", "rb"))
            print("...done.")
        except:
            print("...failed.")
            memory = PrioritizedExperience(
                memory_size=2**14, alpha=alpha0, beta=beta0, window_length=window_size)

        try:
            print("Trying to load 'OU process'", end="")
            random_process = pickle.load(open("random_process.pkl", "rb"))
            print("...done.")
        except:
            print("...failed.")
            random_process = OrnsteinUhlenbeckProcess(
                size=nb_actions, theta=.15, mu=0., sigma=.2, n_steps_annealing=nb_steps)

        memory_filled = memory.tree.filled_size()
        if memory_filled > 1024:
            warmup_steps = 0
        else:
            warmup_steps = 1024

        agent = DDPG_PERAgent(nb_actions=nb_actions, actor=actor, critic=critic, critic_action_input=models.action_input,
                              memory=memory, nb_steps_warmup_critic=warmup_steps, nb_steps_warmup_actor=warmup_steps,
                              random_process=random_process, gamma=.99, target_model_update=1e-3, batch_size=16, processor=processor, delta_clip=1000)

        agent.compile([Adam(lr=1e-4), Adam(lr=1e-3)], metrics=['mae'])

        try:
            print("Trying to load 'agent weights'", end="")
            agent.load_weights('ddpg_' + ENV_NAME + '_weights.h5f')
            print("...done.")
        except:
            print("...failed.")

        try:
            print("Trying to load 'agent steps'", end="")
            nb_steps_done = pickle.load(open("steps.pkl", "rb"))
            print("...done.")
        except:
            nb_steps_done = 0
            print("...failed.")

        print("{}/{} steps completed. Continuing...".format(nb_steps_done, nb_steps))

        agent.step = nb_steps_done

        train_history = agent.fit(env, nb_steps=nb_steps-nb_steps_done, visualize=False,
                                  verbose=1, action_repetition=4, callbacks=callbacks)

        if agent.step == nb_steps:
            print("Steps done: {}/{}".format(agent.step, nb_steps))
            break

    except KeyboardInterrupt:
        tb.print_exc()
        env.close_client_and_server()
        break
    except:
        tb.print_exc()
        # env.close_client_and_server()
    finally:
        print("Saving...'weights'", end="")
        agent.save_weights('ddpg_' + ENV_NAME + '_weights.h5f', overwrite=True)
        print("..'memory'..", end="")
        pickle.dump(memory, open("memory.pkl", "wb"))
        print("..'OU process'..", end="")
        pickle.dump(random_process, open("random_process.pkl", "wb"))
        print("..'steps'..", end="")
        pickle.dump(agent.step, open("steps.pkl", "wb"))
        print("..done")
        # env.close_client_and_server()
