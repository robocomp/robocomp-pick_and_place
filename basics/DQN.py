import gym
import math
import random
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from collections import namedtuple, deque
from itertools import count
from PIL import Image

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torchvision.transforms as T

from EnvKinova_gym import EnvKinova_gym
import q_aux as QA

env = EnvKinova_gym()

# set up matplotlib
is_ipython = 'inline' in matplotlib.get_backend()
if is_ipython:
    from IPython import display

plt.ion()

# if gpu is to be used
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

Transition = namedtuple('Transition', ('state', 'action', 'next_state', 'reward'))


class ReplayMemory(object):

    def __init__(self, capacity):
        self.memory = deque([],maxlen=capacity)

    def push(self, *args):
        self.memory.append(Transition(*args))

    def sample(self, batch_size):
        return random.sample(self.memory, batch_size)

    def __len__(self):
        return len(self.memory)


class DQN(nn.Module):

    def __init__(self, n_imputs, n_outputs):
        super(DQN, self).__init__()
        self.l1 = nn.Linear(n_imputs, 12)
        self.l2 = nn.Linear(12, n_outputs)
        self.l3 = nn.Softmax()

    def forward(self, x):
        print("ENTRADA", x.shape)
        x = torch.Tensor(x).to(device)
        print("TENSOR", x.shape)
        x = F.relu(self.l1(x))
        print("L1", x.shape)
        x = F.relu(self.l2(x))
        print("L2", x.shape)
        x = self.l3(x)
        print("L3", x.shape)
        return x


BATCH_SIZE = 128
GAMMA = 0.999
EPS_START = 0.9
EPS_END = 0.05
EPS_DECAY = 200
TARGET_UPDATE = 10
EPOCHS = 50

# Get number of actions from gym action space
n_actions = env.action_space.n
print("NACTIONS :::: ", n_actions)

policy_net = DQN(2, n_actions).to(device)
target_net = DQN(2, n_actions).to(device)
target_net.load_state_dict(policy_net.state_dict())
target_net.eval()

optimizer = optim.RMSprop(policy_net.parameters())
memory = ReplayMemory(10000)


steps_done = 0

def select_action(state):
    global steps_done
    sample = random.random()
    eps_threshold = EPS_END + (EPS_START - EPS_END) * math.exp(-1. * steps_done / EPS_DECAY)
    steps_done += 1
    if sample > eps_threshold:
        with torch.no_grad():
            return policy_net(state).max().view(1, 1)
    else:
        return torch.tensor([[random.randrange(n_actions)]], device=device, dtype=torch.long)


episode_durations = []

def plot_durations():
    plt.figure(2)
    plt.clf()
    durations_t = torch.tensor(episode_durations, dtype=torch.float)
    plt.title('Training...')
    plt.xlabel('Episode')
    plt.ylabel('Duration')
    plt.plot(durations_t.numpy())
    
    if len(durations_t) >= 100:  # Take 100 episode averages and plot them too
        means = durations_t.unfold(0, 100, 1).mean(1).view(-1)
        means = torch.cat((torch.zeros(99), means))
        plt.plot(means.numpy())

    plt.pause(0.001)  # pause a bit so that plots are updated
    if is_ipython:
        display.clear_output(wait=True)
        display.display(plt.gcf())

def optimize_model():
    if len(memory) < BATCH_SIZE:
        return
    transitions = memory.sample(BATCH_SIZE)
    batch = Transition(*zip(*transitions))

    print(type(batch.next_state), batch.next_state)
    non_final_mask = torch.Tensor([t.numpy() for t in batch.next_state])
    non_final_next_states = torch.cat(batch.next_state)

    # print(type(batch.state))
    state_batch = torch.cat(batch.state)
    action_batch = torch.cat(batch.action)
    reward_batch = torch.cat(batch.reward)
    
    print("AAAAAAAAAAAAAA")
    aux_list = [policy_net(s) for s in list(batch.state)]
    print(len(aux_list))
    state_action_values = aux_list.gather(1, action_batch)
    

    print("EEEEEEEEEEEEEE")
    next_state_values = torch.zeros(BATCH_SIZE, device=device)
    next_state_values[non_final_mask] = [target_net(t).max() for t in non_final_next_states]
    expected_state_action_values = (next_state_values * GAMMA) + reward_batch

    # Loss
    criterion = nn.SmoothL1Loss()
    loss = criterion(state_action_values, expected_state_action_values.unsqueeze(1))

    # Optimization
    optimizer.zero_grad()
    loss.backward()
    for param in policy_net.parameters():
        param.grad.data.clamp_(-1, 1)
    optimizer.step()


for i_episode in range(EPOCHS):
    # Initialize the environment and state
    state = env.reset()
    for t in count():
        action = select_action(state)

        # if isinstance(action, int):
        #     action = S.action2index(action)

        next_state, reward, done, _ = env.step(QA.index2action(int(action.item())))
        reward = torch.tensor([reward], device=device)

        # Store the transition in memory
        memory.push(torch.Tensor(state), action, torch.Tensor(next_state), reward)

        # Move to the next state
        state = next_state

        # Perform one step of the optimization (on the policy network)
        optimize_model()
        if done:
            episode_durations.append(t + 1)
            plot_durations()
            break
    # Update the target network, copying all weights and biases in DQN
    if i_episode % TARGET_UPDATE == 0:
        target_net.load_state_dict(policy_net.state_dict())

print('Complete')
env.render()
env.close()
plt.ioff()
plt.show()

# TODO Save ANNs
