from weakref import WeakKeyDictionary

# all the events

class Event():
    '''
    superclass for events
    '''
    name = 'Default Event'
    client_number = None
    send_over_network = False

class TickEvent(Event):
    ''' update the game! gets created 60 times a sec '''
    def __init__(self, delta_time):
        self.name = 'Tick Event'
        self.delta_time = delta_time

class NewClientConnectedEvent(Event):
    '''
    used by the server to know when a new
    client connects
    '''
    def __init__(self, client_number, client_ip):
        self.name = 'New Client Connected Event'
        self.client_number = client_number
        self.client_ip = client_ip

class TextMessageEvent(Event):
    ''' Just text '''
    def __init__(self, text, send_over_network):
        self.name = 'Text Message Event'
        self.text = text # any string
        self.send_over_network = send_over_network # True or False

class CompleteGameStateEvent(Event):
    '''
    Holds the  visual info for every
    object in the game
    '''
    # example of game state list
    # [['OBJECT NAME', id, [position]], object2, object3...
    # [['CHARACTER', 19376408, [300, 300]], ect... ]
    def __init__(self, game_state):
        self.name = 'Complete Game State Event'
        self.game_state = game_state
        self.send_over_network = True

class CharacterStatesEvent(Event):
    '''
    Holds the info for every
    character in the game
    server to client and
    internal client only
    '''
    # example of game state list
    # [['OBJECT NAME', id, [position]], object2, object3...
    # [['CHARACTER', 19376408, [300, 300]], ect... ]
    def __init__(self, character_states):
        self.name = 'Character States Event'
        self.character_states = character_states

class CompleteGameStateRequestEvent(Event):
    def __init__(self):
        self.name = 'Complete Game State Request Event'
        self.send_over_network = True

##### USER INPUT EVENTS #####
class UserMouseInputEvent(Event):
    '''
    when the user clicks down on the mouse
    '''
    def __init__(self, mouse_button, mouse_position):
        self.name = 'User Mouse Input Event'
        self.mouse_button = mouse_button
        self.mouse_position = mouse_position

class UserKeyboardInputEvent(Event):
    '''
    When the user presses keyboard keys
    generated by the KeyboardController
    '''
    def __init__(self, keyboard_input, client_number = None):  
        self.name = 'User Keyboard Input Event'
        self.keyboard_input = keyboard_input
        self.client_number = client_number # server uses this to track which client's input it was
        self.send_over_network = True

class PlaceWallRequestEvent(Event):
    '''
    when the user clicks and wants to place a new wall
    '''
    def __init__(self, grid_position, client_number = None):
        self.name = 'Place Wall Request Event'
        self.grid_position = grid_position
        self.client_number = client_number # server uses this to track which client's input it was
        self.send_over_network = True
        
class EventEncoder():
    def __init__(self):
        pass

    def encode_event(self, event):
        if event.name == 'Text Message Event':
            encoded_event = []
            dict_event = {'name': 'Text Message Event',
                          'text': event.text}
            event_list.append(dict_event)
            return encoded_event
        
        elif event.name == 'User Keyboard Input Event':
            encoded_event = []
            dict_event = {'name': 'User Keyboard Input Event',
                          'input': event.keyboard_input}
            encoded_event.append(dict_event)
            return encoded_event

        elif event.name == 'Place Wall Request Event':
            encoded_event = []
            dict_event = {'name': 'Place Wall Request Event',
                          'grid_position': event.grid_position}
            encoded_event.append(dict_event)
            return encoded_event
                          

        else:
            print 'The event <' + event.name + '> cannot be encoded by the EventEncoder!'
        
    def decode_event(self, encoded_event, client_number = None):
        '''
        event: [{'input': 'LEFT', 'name': 'User Keyboard Input Event'}]
        returns: Event instance
        '''
        #### DOES RETURNING INSIDE A FOR LOOP BREAK THINGS??? ####
        for e in encoded_event:
            if e['name'] == 'User Keyboard Input Event':
                event = UserKeyboardInputEvent(e['input'], client_number)
                return event
            elif e['name'] == 'Place Wall Request Event':
                event = PlaceWallRequestEvent(e['grid_position'], client_number)
                return event


class EventManager():
    '''
    acts as the connection between all the different program elements,
    all events are sent through here.
    '''
    def __init__(self):
        self.listeners = WeakKeyDictionary() # holds our listeners
        self.event_queue = []

    def add_listener(self, listener):
        self.listeners[listener] = True

    def remove_listener(self, listener):
        if listener in self.listeners:
            del self.listeners[listener]

    def post(self, event):
        self._add_event_to_queue(event)
        if event.name == 'Tick Event':
            self._process_event_queue()

    def _add_event_to_queue(self, event):
        self.event_queue.append(event)

    def _process_event_queue(self):
        event_number = 0
        while event_number < len(self.event_queue):
            event = self.event_queue[event_number]
            event_number += 1
            for listener in self.listeners:
                listener.notify(event)
        self.event_queue = []

