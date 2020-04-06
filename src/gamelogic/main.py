#          .x+=:.                     ..    .         s                   .                        
#     z`    ^%              x .d88"    @88>      :8                  @88>                          
#        .   <k        u.    5888R     %8P      .88                  %8P      .u    .              
#      .@8Ned8"  ...ue888b   '888R      .      :888ooo       u        .     .d88B :@8c       .u    
#    .@^%8888"   888R Y888r   888R    .@88u  -*8888888    us888u.   .@88u  ="8888f8888r   ud8888.  
#   x88:  `)8b.  888R I888>   888R   ''888E`   8888    .@88 "8888" ''888E`   4888>'88"  :888'8888. 
#   8888N=*8888  888R I888>   888R     888E    8888    9888  9888    888E    4888> '    d888 '88%" 
#    %8"    R88  888R I888>   888R     888E    8888    9888  9888    888E    4888>      8888.+"    
#     @8Wou 9%  u8888cJ888    888R     888E   .8888Lu= 9888  9888    888E   .d888L .+   8888L      
#   .888888P`    "*888*P"    .888B .   888&   ^%888*   9888  9888    888&   ^"8888*"    '8888c. .+ 
#   `   ^"F        'Y"       ^*888%    R888"    'Y"    "888*""888"   R888"     "Y"       "88888%   
#                              "%       ""              ^Y"   ^Y'     ""                   "YP'    
#    
#   62410 CDIO-Projekt F20 - Solitaire solver
#   https://github.com/MaxTheScrub/CDIO_Project 
#
#   Group 7:                                    
#   Henrik Peter Warncke s184801                
#   Max Feng Chen Bjørnsen s184811              
#   Jeppe Møller Bak s164871                    
#   Adam Aron Edelsten s173057                  
#   Tobias Lauge Borgstrøm s184810              
#   Tobias Ladefoged Jensen s184815             
#   Markus Repnak Jacobsen s184808              
#   Ajs Ritsmer Stormholt s174517               
#
#   Naming convention: https://www.python.org/dev/peps/pep-0008/                       
#   Class names: PascalCase                         
#   Function names: snake_case                       
#   Variables: camelCase
#   Objects: camelCase                        
#   Constants: SCREAMING_SNAKE_CASE             

from testing import *
from prediction import *
from classes import *

# Code runs here 
setup_table()
# print_cards()
# print_table()
tableauPiles[1].frontCard.value = Value(1)
tableauPiles[1].frontCard.suit = Suit(3)
tableauPiles[1].frontCard.color = Color.BLACK
tableauPiles[3].frontCard.value = Value(2)
tableauPiles[3].frontCard.suit = Suit(3)
tableauPiles[3].frontCard.color = Color.BLACK
# insert_card(Value(8), Suit(3), Pile.TABLEAU, Color.BLACK, tableauPiles[1])
# insert_card(Value(7), Suit(0), Pile.TABLEAU, Color.RED, tableauPiles[1])
print_table()
#print_cards()
#start_add_to_tableau([tableauPiles[1].cards[LAST_INDEX]], tableauPiles[1], tableauPiles[3])
again = 0
while again != '1':
    print_table()
    give_advice_and_do(tableauPiles, stock, foundationsPiles, lowestNeededCard)
    win_check()
    again = input("If you want to stop press 1 ")