grammar Manifest;

/*
Note: You must use a separate rule when you have multiple instances of a
specific case of a general rule, as you cannot use the same label more than
once. Labels are can only refer to a single rule in ANTLR-generated parsers -
later instances of a label on a single rule overwrite earlier ones.
*/

/* Expressions
-------------------------------------------------- */

manifest : ( ( explScopedContext
             | implScopedContext
             | declaration
             | comment
             )
             (NEWLINE+ | EOF)
           )* ;

explScopedContext : contextHeader SPACE? blockOpen
                      NEWLINE*
                      ( SPACE? (explScopedContext | implScopedContext) NEWLINE*
                      | SPACE? declaration NEWLINE+
                      | comment NEWLINE+
                      )*
                    blockClose ;
implScopedContext : contextHeader comment? NEWLINE
                    ( SPACE? explScopedContext NEWLINE
                    | SPACE? implScopedContext
                    | SPACE? declaration NEWLINE
                    | comment NEWLINE
                    )* ;
contextHeader : CONTEXT_OPEN typeName=NAME (SPACE? dataOpen
                  (comment NEWLINE SPACE?)*
                  contextOpt
                  ( dataItemSeparator
                    (comment NEWLINE SPACE?)*
                    contextOpt
                  )*
                  (NEWLINE SPACE? comment)*
                dataClose)? ;
contextOpt : kvPair comment? ;

declaration : (item | itemSet) comment? ;

/* Declarations
-------------------- */

item : ref (SPACE dataOpen
         tag (dataItemSeparator tag)*
       dataClose)? ;
itemSet : ref SPACE setOpen itemSetList setClose ;
itemSetList : ref                                     #setItemSet
            | tag                                     #setTag
            | setOpen itemSetList setClose            #setGroup
            | itemSetList setItemOperator itemSetList #setOp
            ;
ref : LITERAL_WRAPPER refLiteral LITERAL_WRAPPER | refNormal ;
refLiteral : ~LITERAL_WRAPPER+ ;
refNormal : NAME | PATH ;
tag : kvPair ;

/* Primitives
-------------------- */

kvPair : name=NAME (kvSeparator value=toEndOfItem)? ;
kvSeparator : SPACE? KEY_VALUE_SEPARATOR SPACE? ;

blockOpen : BLOCK_OPEN comment? NEWLINE? SPACE? ;
blockClose : NEWLINE? SPACE? BLOCK_CLOSE comment? ;
blockItemSeparator : comment? NEWLINE SPACE? ;

dataOpen : DATA_OPEN comment? NEWLINE? SPACE? ;
dataClose : NEWLINE? SPACE? DATA_CLOSE comment? ;
dataItemSeparator : ( DATA_ITEM_SEPARATOR
                    | comment? NEWLINE
                    | DATA_ITEM_SEPARATOR comment? NEWLINE
                    ) SPACE? ;

setOpen : SET_OPEN comment? NEWLINE? SPACE? ;
setClose : NEWLINE? SPACE? SET_CLOSE comment? ;
setItemOperator : (comment? NEWLINE)?
                  SPACE? SET_ITEM_OPERATOR
                  (comment? NEWLINE)? SPACE? ;

comment : SPACE? COMMENT_OPEN text=toEndOfLine ;

/* Utils
-------------------- */

toEndOfItem : ~( NEWLINE 
               | DATA_ITEM_SEPARATOR
               | SET_ITEM_OPERATOR
               | DATA_CLOSE
               | SET_CLOSE
               )* ;
toEndOfLine : ~NEWLINE* ;

/* Tokens
-------------------------------------------------- */

// Whitespace
NEWLINE : NEWLINE_CHAR ;
SPACE : SPACE_CHAR+ ;

// General
COMMENT_OPEN : '#' ;
CONTEXT_OPEN : '@' ;

BLOCK_OPEN : '{' ;
BLOCK_CLOSE : '}' ;

DATA_OPEN : '(' ;
DATA_CLOSE : ')' ;
DATA_ITEM_SEPARATOR : ',' ;

SET_OPEN : '[' ;
SET_CLOSE : ']' ;
SET_ITEM_OPERATOR : [&|] ;

KEY_VALUE_SEPARATOR : ':' ;

// Names and values
LITERAL_WRAPPER : '"""' ;
NAME : NAME_CHAR+ ;
PATH : PATH_CHAR+ ;

// Misc (eg. for comment text and context values)
OTHER : . ;

/* Character Classes
-------------------------------------------------- */

fragment NEWLINE_CHAR : ('\r'? '\n' | '\r') ;
fragment SPACE_CHAR : [\t ] ;

/* Other chars (like  #@()[],&:  and space) will require tripple quoting, where
   available */
fragment NAME_CHAR : [A-Za-z0-9_\-] ;
fragment PATH_CHAR : [A-Za-z0-9_\-.'/] ;
