import numpy as np
import random
import torch
import torch.nn.functional as F

from ddpg.models import ActorNet, CriticNet
from utils.buffer import ReplayBuffer
from utils.noise import OUNoise
from utils.utils import soft_update, tensor

class Agent():
    def __init__(self, num_agents, state_size, action_size, opts):
        self.num_agents = num_agents
        self.state_size = state_size
        self.action_size = action_size
        self.opts = opts
        self.closs = np.inf
        self.aloss = np.inf  

        self.eps = 1
        self.eps_decay = 0.998
        self.min_eps = 0.01

        # Actor Network 
        self.actor_local = ActorNet(state_size, action_size, 
                            fc1_units=opts.a_fc1, fc2_units=opts.a_fc2).to(opts.device)
        self.actor_target = ActorNet(state_size, action_size,
                            fc1_units=opts.a_fc1, fc2_units=opts.a_fc2).to(opts.device)
        self.actor_optimizer = torch.optim.Adam(self.actor_local.parameters(), lr=opts.actor_lr)

        # Critic Network 
        self.critic_local = CriticNet(state_size, action_size,
                            fc1_units=opts.c_fc1, fc2_units=opts.c_fc2).to(opts.device)
        self.critic_target = CriticNet(state_size, action_size,
                            fc1_units=opts.c_fc1, fc2_units=opts.c_fc2).to(opts.device)
        self.critic_optimizer = torch.optim.Adam(self.critic_local.parameters(), lr=opts.critic_lr, weight_decay=opts.critic_weight_decay)

        # Noise process
        self.noise = OUNoise((num_agents,action_size), opts.random_seed)
        self.step_idx = 0

        # Replay memory
        self.memory = ReplayBuffer(action_size, opts.buffer_size, opts.batch_size, opts.random_seed, opts.device)

    def finish_episode(self):
        self.eps *= self.eps_decay
        self.eps = max(self.eps, self.min_eps)
        self.noise.reset()    

    def step(self, state, action, reward, next_state, done, warmup):
        for i in range(self.num_agents): 
            self.memory.add(state[i,:], action[i,:], reward[i], next_state[i,:], done[i])
        
        self.step_idx += 1            
        is_learn_iteration = (self.step_idx % self.opts.learn_every ) == 0
        is_update_iteration = ( self.step_idx % self.opts.update_every ) == 0
        
        if warmup:
            return

        if len(self.memory) > self.opts.batch_size:
            if is_learn_iteration:
                for _ in range(self.opts.learn_iterations): 
                    experiences = self.memory.sample()
                    self.learn(experiences, self.opts.gamma)
        
                    if is_update_iteration:
                        soft_update(self.critic_local, self.critic_target, self.opts.tau) 
                        soft_update(self.actor_local, self.actor_target, self.opts.tau)

    def act(self, state, warmup):
        state = torch.from_numpy(state).float().to(self.opts.device)

        noise = self.noise.sample()
        noise *= self.eps

        if warmup:
            action = noise
        else:
            self.actor_local.eval()
            with torch.no_grad():
                action = self.actor_local(state).cpu().data.numpy()
            self.actor_local.train()

            if np.random.random() < self.eps:
                action += noise
        
        return np.clip(action, self.opts.minimum_action_value, self.opts.maximum_action_value)

    def save(self):       
        torch.save(self.critic_local.state_dict(),
                   self.opts.output_data_path+"critic_local.pth")
        torch.save(self.critic_target.state_dict(),
                    self.opts.output_data_path+"critic_target.pth")
        torch.save(self.actor_local.state_dict(),
                    self.opts.output_data_path+"actor_local.pth")
        torch.save(self.actor_target.state_dict(),
                    self.opts.output_data_path+"actor_target.pth")

    def learn(self, experiences, gamma):
        states, actions, rewards, next_states, dones = experiences

        states = tensor(states, self.opts.device)
        actions = tensor(actions, self.opts.device)
        rewards = tensor(rewards, self.opts.device)
        next_states = tensor(next_states, self.opts.device)
        mask = tensor(1 - dones, self.opts.device)

        # Update critic
        actions_next = self.actor_target(next_states)
        Q_targets_next = self.critic_target(next_states, actions_next)
        Q_targets = rewards + (gamma * Q_targets_next * mask)

        # Compute & minimize critic loss
        Q_expected = self.critic_local(states, actions)
        critic_loss = F.mse_loss(Q_expected, Q_targets)
        closs = float(critic_loss)
        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.critic_local.parameters(), 1)
        self.critic_optimizer.step()

        # Update actor
        actions_pred = self.actor_local(states)

        # Compute & minimize critic loss
        actor_loss = -self.critic_local(states, actions_pred).mean()
        aloss = float(actor_loss)
        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        self.actor_optimizer.step() 

        self.closs = closs
        self.aloss = aloss   