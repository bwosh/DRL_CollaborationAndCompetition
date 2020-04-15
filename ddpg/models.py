import numpy as np 

import torch
import torch.nn as nn
import torch.nn.functional as F

from utils.utils import hidden_init

class ActorNet(nn.Module):
    def __init__(self, state_size, action_size, fc1_units=128, fc2_units=128):
        super(ActorNet, self).__init__()
        self.fc1_units = fc1_units
        self.fc2_units = fc2_units

        self.fc1 = nn.Linear(state_size, fc1_units)
        self.fc2 = nn.Linear(fc1_units, fc2_units)
        self.fc3 = nn.Linear(fc2_units, action_size)

        self.reset_parameters()

    def reset_parameters(self):
        self.fc1.weight.data.uniform_(*hidden_init(self.fc1))
        self.fc2.weight.data.uniform_(*hidden_init(self.fc2))
        self.fc3.weight.data.uniform_(-3e-3, 3e-3)

    def forward(self, state):
        x = F.relu(self.fc1(state))
        x = F.relu(self.fc2(x))
        return torch.tanh(self.fc3(x))


class CriticNet(nn.Module):
    def __init__(self, state_size, action_size, fc1_units=128, fc2_units=128):
        super(CriticNet, self).__init__()

        self.fc1_units = fc1_units
        self.fc2_units = fc2_units

        self.fc1 = nn.Linear(state_size, fc1_units)
        self.fc2 = nn.Linear(fc1_units + action_size, fc2_units)
        self.fc3 = nn.Linear(fc2_units, action_size)

        self.reset_parameters()

    def reset_parameters(self):
        self.fc1.weight.data.uniform_(*hidden_init(self.fc1))
        self.fc2.weight.data.uniform_(*hidden_init(self.fc2))
        self.fc3.weight.data.uniform_(-3e-3, 3e-3)

    def forward(self, state, action):
        x = F.relu(self.fc1(state))
        x = torch.cat([x, action], dim=1)
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x