import os
import time
import pygame
from pygame.locals import *
from twisted.spread import pb
from twisted.internet.selectreactor import SelectReactor
from twisted.internet.main import installReactor

from weakref import WeakKeyDictionary


class Event():
    '''
    superclass for events
    '''
    def __init__(self):
        self.name = 'Default Event'

class TickEvent(Event):
    '''
    frame rate tick
    '''
    def __init__(self, delta_time):
        self.name = 'Tick Event'
        self.delta_time = delta_time

class RenderEvent(Event):
    '''
    render the screen
    '''
    def __init__(self):
        self.name = 'Render Event'

class ProgramQuitEvent(Event):
    '''
    when we quit the program
    '''
    def __init__(self):
        self.name = 'Program Quit Event'

class GameStartRequestEvent(Event):
    def __init__(self):
        self.name = 'Game Start Request Event'

class GameStartedEvent(Event):
    '''
    the game has started
    '''
    def __init__(self, game):
        self.name = 'Game Started'
        self.game = game

# generated by the keyboard controller
class UserKeyboardInputEvent(Event):
    '''
    When the user presses keyboard keys
    generated by the KeyboardController
    Not sent over the network
    '''
    def __init__(self, keyboard_input):  
        self.name = 'User Keyboard Input Event'
        self.keyboard_input = keyboard_input

class UserMouseInputEvent(Event):
    '''
    when the user clicks down on the mouse
    '''
    def __init__(self, mouse_button, mouse_position):
        self.name = 'User Mouse Input Event'
        self.mouse_button = mouse_button
        self.mouse_position = mouse_position

# client to server requests
class CharacterMoveRequestEvent(Event):
    '''
    when a character moves in a direction
    '''
    def __init__(self, character_id, direction):
        self.name = 'Character Move Request Event'
        self.character_id = character_id
        self.direction = direction

class CreateProjectileRequestEvent(Event):
    '''
    when the character clicks down to shoot a
    projectile
    '''
    def __init__(self, starting_position, target_position, emitter_id):
        self.name = 'Create Projectile Request Event'
        self.starting_position = starting_position
        self.target_position = target_position
        self.emitter_id = emitter_id

class ServerConnectEvent(Event):
    def __init__(self, serverReference):
        self.name = 'Server Connect Event'
        self.server = serverReference


class ClientConnectEvent(Event):
    def __init__(self, client):
        self.name = 'Client Connect Event'
        self.client = client

copyable_events = {}

server_to_client_events = []
client_to_server_events = []

######################## Stuff from network.py
def MixInClass(origClass, addClass):
    if addClass not in origClass.__bases__:
        origClass.__bases__ += (addClass,)

def MixInCopyClasses(someClass):
    MixInClass(someClass, pb.Copyable)
    MixInClass(someClass, pb.RemoteCopy)

# this makes these classes an instance of pb.copyable
# so they can be sent over the network
#client to server
MixInCopyClasses(ProgramQuitEvent)
pb.setUnjellyableForClass(ProgramQuitEvent, ProgramQuitEvent)
client_to_server_events.append(ProgramQuitEvent)

#client to server
MixInCopyClasses(GameStartRequestEvent)
pb.setUnjellyableForClass(GameStartRequestEvent, GameStartRequestEvent)
client_to_server_events.append(GameStartRequestEvent)


class CopyableProgramQuitEvent(pb.Copyable, pb.RemoteCopy):
    '''client to server only'''
    def __init__(self, event, object_registry):
        self.name = 'Copyable Program Quit Event'
        
class CopyableGameStartedEvent(pb.Copyable, pb.RemoteCopy):
    '''server to client only'''
    def __init__(self, event, object_registry):
        self.name = 'Copyable Game Started Event'
        self.game_id = id(event.game)
        object_registry[self.game_id] = event.game

pb.setUnjellyableForClass(CopyableGameStartedEvent, CopyableGameStartedEvent)
server_to_client_events.append(CopyableGameStartedEvent)

class CopyableCompleteGameStateEvent(pb.Copyable, pb.RemoteCopy):
    '''server to client only'''
    def __init__(self, event, object_registry):
        self.name = 'Copyable Complete Game State Event'
        self.game_state = event.game_state

pb.setUnjellyableForClass(CopyableCompleteGameStateEvent, CopyableCompleteGameStateEvent)
server_to_client_events.append(CopyableCompleteGameStateEvent)

class CopyableCharacterMoveRequestEvent(pb.Copyable, pb.RemoteCopy):
    def __init__(self, event, object_registry):
        self.name = 'Copyable Character Move Request Event'
        self.character_id = event.character_id
        self.direction = event.direction

pb.setUnjellyableForClass(CopyableCharacterMoveRequestEvent, CopyableCharacterMoveRequestEvent)
client_to_server_events.append(CopyableCharacterMoveRequestEvent)

class CopyableCreateProjectileRequestEvent(pb.Copyable, pb.RemoteCopy):
    '''
    when the character clicks down to shoot a
    projectile
    '''
    def __init__(self, event, object_registry):
        self.name = 'Copyable Create Projectile Request Event'
        self.starting_position = event.starting_position
        self.target_position = event.target_position
        self.emitter_id = event.emitter_id

pb.setUnjellyableForClass(CopyableCreateProjectileRequestEvent, CopyableCreateProjectileRequestEvent)
client_to_server_events.append(CopyableCreateProjectileRequestEvent)

# add the keys and classes to the copyable_events dictionary
copyable_events['CopyableGameStartedEvent'] = CopyableGameStartedEvent
copyable_events['CopyableCompleteGameStateEvent'] = CopyableCompleteGameStateEvent
copyable_events['CopyableCharacterMoveRequestEvent'] = CopyableCharacterMoveRequestEvent
copyable_events['CopyableCreateProjectileRequestEvent'] = CopyableCreateProjectileRequestEvent


class EventManager():
    '''super class event manager'''
    def __init__(self):
        self.listeners = WeakKeyDictionary()
        self.event_queue = []

    def register_listener(self, listener):
        self.listeners[listener] = True

    def unregister_listener(self, listener):
        if listener in self.listeners:
            del self.listeners[listener]
    def post(self, event):
        self.event_queue.append(event)
        if isinstance(event, TickEvent):
            self._process_event_queue()
        else:
            pass

    def _process_event_queue(self):
        # goes through all the events and sends them to the listeners
        event_number = 0
        while event_number < len(self.event_queue):
            event = self.event_queue[event_number]
            for listener in self.listeners:
                listener.notify(event)
            event_number += 1
        # empty the queue
        self.event_queue = []

       
######################################

        
class NetworkServerView(pb.Root):
    ''' Used to send events to the Server'''

    def __init__(self, eventManager, object_registry):
        self.eventManager = eventManager
        self.eventManager.register_listener(self)

        self.pbClientFactory = pb.PBClientFactory()
        self.state = 'PREPARING'
        self.reactor = None
        self.server = None

        self.object_registry = object_registry

    def attempt_connection(self):
        print 'Attempting connection...'
        self.state = 'CONNECTING'
        if self.reactor:
            self.reactor.stop()
            self.pump_reactor()
        else:
            self.reactor = SelectReactor()
            installReactor(self.reactor)
            connection = self.reactor.connectTCP('localhost', 24100, self.pbClientFactory)
            deferred = self.pbClientFactory.getRootObject()
            deferred.addCallback(self.connected)
            deferred.addErrback(self.connect_failed)
            self.reactor.startRunning()

    def disconnect(self):
        print 'disconnecting...'
        if not self.reactor:
            return
        print 'stopping the client reactor...'
        self.reactor.stop()
        self.pump_reactor()
        self.state = 'DISCONNECTING'

    def connected(self, server):
        print '...connected!'
        self.server = server
        self.state = 'CONNECTED'
        newEvent = ServerConnectEvent(server)
        self.eventManager.post(newEvent)

    def connect_failed(self, server):
        print '...Connection failed'
        self.state = 'DISCONNECTED'

    def pump_reactor(self):
        self.reactor.runUntilCurrent()
        self.reactor.doIteration(False)
        
    def notify(self, event):
        if isinstance(event, TickEvent):
            if self.state == 'PREPARING':
                self.attempt_connection()
            elif self.state in ['CONNECTED', 'DISCONNECTING', 'CONNECTING']:
                self.pump_reactor()
            return
                
        if isinstance(event, ProgramQuitEvent):
            self.disconnect()
            return

        testing_event = event

        if not isinstance(testing_event, pb.Copyable):
            event_name = testing_event.__class__.__name__
            copyable_class_name = 'Copyable' + event_name
            if copyable_class_name not in copyable_events:
                return
            
            copyable_class = copyable_events[copyable_class_name]
            testing_event = copyable_class(testing_event, self.object_registry)

        else:
            pass
        # see if the event is in our list of things we can send          
        if testing_event.__class__ in client_to_server_events:
            # we can send if its in the list
            if self.server:
                remoteCall = self.server.callRemote('EventOverNetwork', testing_event)
            else:
                pass
        else:
            pass

class NetworkServerController(pb.Referenceable):
    '''Recieves events from the Server'''
    def __init__(self, eventManager):
        self.eventManager = eventManager
        self.eventManager.register_listener(self)

    def remote_RecieveEvent(self, event):
        # the server calls this function to send an event
        # print 'Event recieved from server:', event.name
        self.eventManager.post(event)
        return True

    def notify(self, event):
        if isinstance(event, ServerConnectEvent):
            event.server.callRemote('ClientConnect', self)

class CPUSpinnerController():
    '''
    sends events to the event manager to update all event listeners
    uses python time.time() to get the delta time.
    The delta time (change in time since the last current time) is
    sent to the TickEvent. Different parts of the program use delta
    time to determine how far ahead it needs to step
    (this is used especially in the game physics)
    '''
    def __init__(self, eventManager):
        self.eventManager = eventManager
        self.eventManager.register_listener(self)
        self.clock = pygame.time.Clock() # create a clock
        
        self.program_time = 0.0
        self.initial_time = time.time()
        self.current_time = self.initial_time
        self.delta_time = 0.01 # not sure why .01
        self.extra_time_accumulator = self.delta_time
        self.FPS = 40
        self.minimum_FPS = 4

        self.running = True

    def run(self):
        while self.running:
            pygame.display.set_caption(str(self.clock.get_fps()))
            self.clock.tick(self.FPS)
            
            self.last_time = self.current_time # set last time
            self.current_time = time.time() # get current time
            self.delta_time =  self.current_time - self.last_time # get delta time
            if self.delta_time > (1.0 / self.minimum_FPS):
                delta_time = (1.0 / self.minimum_FPS)
                
            self.extra_time_accumulator += self.delta_time

            while self.extra_time_accumulator >= self.delta_time:
                newEvent = TickEvent(self.delta_time)
                self.program_time += self.delta_time
                self.extra_time_accumulator -= self.delta_time
                newEvent = TickEvent(self.delta_time)
                self.eventManager.post(newEvent)

            newEvent = RenderEvent()
            self.eventManager.post(newEvent)
            
    def notify(self, event):
        if isinstance(event, ProgramQuitEvent):
            self.running = False

################################################################################

class KeyboardController():
    ''' gets user input from the mouse and keyboard'''
    def __init__(self, eventManager):
        self.eventManager = eventManager
        self.eventManager.register_listener(self)
        self.shooting = True

    def notify(self, event):
        if isinstance(event, TickEvent):
            #go through the user input
            for event in pygame.event.get():
                newEvent = None
                if event.type == QUIT:
                    newEvent = ProgramQuitEvent()
                elif event.type == KEYDOWN:
                    if event.key in [pygame.K_ESCAPE]:
                        newEvent = ProgramQuitEvent()

                elif event.type == pygame.MOUSEBUTTONDOWN: # all the mouse down events
                    if event.button == 3: # right mouse button
                        self.shooting = False
                        mouse_button = 'RIGHT'
                        mouse_position = event.pos
                        pass
                    elif event.button == 1: # left mouse button
                        self.shooting = True
                        mouse_button = 'LEFT'
                        mouse_position = event.pos
                        newEvent = UserMouseInputEvent(mouse_button, mouse_position)

                if self.shooting == True:
                    newEvent = UserMouseInputEvent('LEFT', pygame.mouse.get_pos())


                if newEvent:
                    self.eventManager.post(newEvent)
                

            #getting arrow key movement
            pressed = pygame.key.get_pressed()
            directionX = pressed[K_d] - pressed[K_a]
            directionY = pressed[K_s] - pressed[K_w]
            
            # ready the direction details
            text_directionX = ''
            text_directionY = ''
            text_direction = ''
            
            if directionX == -1:
                text_directionX = 'LEFT'
            elif directionX == 1:
                text_directionX = 'RIGHT'
            if directionY == -1:
                text_directionY = 'UP'
            elif directionY == 1:
                text_directionY = 'DOWN'
                
            text_direction = text_directionX + text_directionY # put direction into a string
            if text_direction:# if the user pressed a direction
                newEvent = UserKeyboardInputEvent(text_direction)
                self.eventManager.post(newEvent)


class CharacterSprite(pygame.sprite.Sprite):
    def __init__(self, character_id, position, velocity, object_state, group=None):
        pygame.sprite.Sprite.__init__(self, group)
        self.id = character_id

        self.state = object_state

        self.images = {} # dict to hold images

        self.alive_image = pygame.image.load(os.path.join('resources','character.png'))
        self.alive_image.convert()

        self.dead_image = pygame.image.load(os.path.join('resources','character_dead.png'))
        self.dead_image.convert()
        self.images['ALIVE'] = self.alive_image
        self.images['DEAD'] = self.dead_image
        
        self.image = self.images[self.state]
        self.rect = self.image.get_rect()

        self.position = None # position to move to during update
        self.set_position(position)

    def set_position(self, position):
        self.position = position

    def set_velocity(self, velocity):
        self.velocity = velocity

    def set_state(self, state):
        self.state = state

    def update(self, delta_time):
        # if were already using the correct image
        if self.image == self.images[self.state]:
            pass
        else:
            # use the correct image
            self.image = self.images[self.state]
            self.rect = self.image.get_rect()
        # set the position
        self.rect.topleft = self.position

class ProjectileSprite(pygame.sprite.Sprite):
    def __init__(self, projectile_id, position, velocity, object_state, group=None):
        pygame.sprite.Sprite.__init__(self, group)
        self.id = projectile_id

        self.object_state = object_state
        
        self.images = {}
        self.image_alive = pygame.image.load(os.path.join('resources','bulletblue.png'))
        self.image_alive.convert()

        self.image_dying = pygame.image.load(os.path.join('resources','bulletpurple.png'))
        self.image_dying.convert()

        self.image_dead = pygame.image.load(os.path.join('resources','bulletblack.png'))
        self.image_dead.convert()
        
        self.images['ALIVE'] = self.image_alive
        self.images['DYING'] = self.image_dying
        self.images['DEAD'] = self.image_dead

        self.image = self.images[self.object_state]
        self.rect = self.image.get_rect()

        self.positionX = position[0]
        self.positionY = position[1]
        self.set_position(position)

        self.velocity = None
        self.set_velocity(velocity)

    def set_position(self, position):
        self.positionX = position[0]
        self.positionY = position[1]

    def set_velocity(self, velocity):
        self.velocity = velocity

    def set_state(self, state):
        self.object_state = state
        
    def update(self, delta_time):
        #print delta_time

        if self.image != self.images[self.object_state]:
            self.image = self.images[self.object_state]
            self.rect = self.image.get_rect()

        #print self.positionX
        self.positionX += (self.velocity[0] * delta_time) # calculate speed from direction to move and speed constant
        self.positionY += (self.velocity[1] * delta_time)
        self.rect.topleft = ((round(self.positionX),round(self.positionY))) # apply values to object position
        
class PygameView():
    def __init__(self, eventManager, object_registry):
        self.eventManager = eventManager
        self.eventManager.register_listener(self)

        pygame.init()
        self.screen = pygame.display.set_mode((800, 640))
        pygame.display.set_caption('WELCOME')
        self.background = pygame.Surface(self.screen.get_size())
        self.background.fill((120,235,22))
        self.screen.blit(self.background, (0,0))
        pygame.display.flip()
        self.clock = pygame.time.Clock()
        
        self.user_controlled_character = None
        # we need the game state before we can request stuff
        self.game_state_recieved = False 

        self.object_registry = object_registry # holds the object ids and their respective objects

        self.sprites_dictionary = {} # holds object names, and their classes
        self.sprites_dictionary['CHARACTER'] = self._create_new_character_sprite # character index
        self.sprites_dictionary['PROJECTILE'] = self._create_new_projectile_sprite
    
        #create object groups
        self.all_sprites = []
        self.character_sprites = pygame.sprite.RenderUpdates()
        self.projectile_sprites = pygame.sprite.RenderUpdates()

    def _update_game_state(self, game_state):
        # recieved a list of game objects (characters, projectiles, etc...)
        # example of game state list
        # 6
        # [['CHARACTER', 19376408, [300, 300]], ['CHARACTER', 19377248, [300, 300]]]
        for game_object in game_state:
            object_name = game_object[0]
            object_id = game_object[1]
            object_position = game_object[2]
            object_velocity = game_object[3]
            object_state = game_object[4]

            # if the object already exists
            if object_id in self.object_registry:
                current_object = self.object_registry[object_id] # get object
                current_object.set_position(object_position) # set position
                current_object.set_velocity(object_velocity)
                current_object.set_state(object_state)

            # if it doesnt exist
            else:
                # create a new object
                object_class = self.sprites_dictionary[object_name] # get class
                if not self.user_controlled_character: # if we dont controll a character
                    object_is_user_controlled = True
                else:
                    object_is_user_controlled = False # not user controlled
                object_class(object_id, object_position, object_velocity, object_state, object_is_user_controlled) # run the create sprite function
                           
    def _user_wants_to_move_character(self, keyboard_input):
        ''' When the user presses w,a,s, or d:
        aka: when a User Keyboard Input Event is generated
        PygameView.notify() calls this function
        each character sends a move request and
        sends their id
        '''
        if self.user_controlled_character:
            moving_character = self.user_controlled_character
            newEvent = CharacterMoveRequestEvent(moving_character.id, keyboard_input)
            self.eventManager.post(newEvent)

    def _user_wants_to_shoot_projectile(self, target_position):
        if self.user_controlled_character: # if we have a character
            starting_position = self.user_controlled_character.position # get position of character
            emitter_id = self.user_controlled_character.id
            newEvent = CreateProjectileRequestEvent(starting_position, target_position, emitter_id) # create event
            self.eventManager.post(newEvent)

    def move_character(self, character_id, position):
        character_to_move = self.object_registry[character_id]
        character_to_move.set_position(position)


    def get_character_sprite(self, character):
        for c in self.character_sprites:
            return c

    def _create_new_character_sprite(self, character_id, position, projectile_velocity, object_state, object_is_user_controlled):
        #create the new sprite
        newCharacterSprite = CharacterSprite(character_id, position, projectile_velocity, object_state, self.character_sprites)
        self.all_sprites.append(newCharacterSprite)
        #assign the registry slot to the character sprite
        self.object_registry[character_id] = newCharacterSprite
        if object_is_user_controlled: # if the character is going to be user controlled
            if not self.user_controlled_character: # if we dont already have a user controlled
                self.user_controlled_character = newCharacterSprite # set the sprite

    def _create_new_projectile_sprite(self, projectile_id, projectile_position, projectile_velocity, object_state, object_is_user_controlled):
        newProjectileSprite = ProjectileSprite(projectile_id, projectile_position, projectile_velocity, object_state, self.projectile_sprites)
        self.all_sprites.append(newProjectileSprite)
        # assign the registry slot to the projectile sprite
        self.object_registry[projectile_id] = newProjectileSprite

    def notify(self, event):
        if isinstance(event, TickEvent):
            self.screen.blit(self.background, (0,0))
            delta_time = event.delta_time
            for s in self.all_sprites:
                s.update(event.delta_time)

        elif event.name == 'Render Event':
            self.character_sprites.draw(self.screen)
            self.projectile_sprites.draw(self.screen)

            pygame.display.flip()

        # from the server
        elif event.name == 'Copyable Complete Game State Event':
            self._update_game_state(event.game_state)

        # from the user
        elif event.name == 'User Keyboard Input Event':
            if event.keyboard_input in ['UP', 'DOWN', 'LEFT', 'RIGHT',
                                        'LEFTUP', 'RIGHTUP', 'LEFTDOWN',
                                        'RIGHTDOWN']:
                self._user_wants_to_move_character(event.keyboard_input)

        elif event.name == 'User Mouse Input Event':
            if event.mouse_button in ['LEFT']:
                target_position = event.mouse_position
                self._user_wants_to_shoot_projectile(target_position)
            

def main():
    print '############################################'
    print '##### Starting Project Defender Client #####'
    print '############################################'
    print 'Loading...'

    eventManager = EventManager()
    object_registry = {}

    keyboardController = KeyboardController(eventManager)
    spinnerController = CPUSpinnerController(eventManager)

    pygameView = PygameView(eventManager, object_registry)

    serverController = NetworkServerController(eventManager)
    serverView = NetworkServerView(eventManager, object_registry)

    print '...Loading Complete!'
    print 'Running Program...'
    spinnerController.run()
    print '...running complete'

if __name__ == '__main__':
    import cProfile
    cProfile.run('main()')
    #main()
    reactor.stop()
    pygame.quit() # closes the pygame window for us

