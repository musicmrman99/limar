grammar Manifest;

/* Expressions
-------------------------------------------------- */

manifest : (statement? NEWLINE)+ EOF ;
statement : SPACE? (comment | (context | project | projectSet) comment?) ;

comment : COMMENT_OPEN text=toEndOfLine ;

context : BLOCK_NAME_OPEN typeName=NAME (SPACE? contextOpts)? SPACE BLOCK_OPEN NEWLINE
            statement ((NEWLINE SPACE? statement)+)?
          NEWLINE SPACE? BLOCK_CLOSE ;
contextOpts : GROUP_OPEN (
                  contextOpt ((SPACE? GROUP_ITEM_SEPARATOR SPACE? contextOpt)+)?
                | NEWLINE SPACE? contextOpt ((NEWLINE SPACE? contextOpt)+)? NEWLINE
              ) SPACE? GROUP_CLOSE ;
contextOpt : optName=NAME SPACE? NAME_VALUE_SEPARATOR SPACE? optValue=toEndOfGroupItem ;

project : ref (SPACE GROUP_OPEN SPACE? tagList SPACE? GROUP_CLOSE)? ;
projectSet : ref SPACE BLOCK_OPEN SPACE? tagSet SPACE? BLOCK_CLOSE ;
ref : PATH | NAME ;

tagList : tag ((SPACE? GROUP_ITEM_SEPARATOR SPACE? tag)+)? ;
tagSet : tag                                              #tagBase
       | GROUP_OPEN SPACE? tagSet SPACE? GROUP_CLOSE      #tagOpGroup
       | tagSet SPACE? op=TAG_SET_SEPARATOR SPACE? tagSet #tagOp
       ;
tag : NAME ;

// A newline counts as a group item separator
toEndOfGroupItem : ~(GROUP_ITEM_SEPARATOR | NEWLINE | GROUP_CLOSE)+ ;
toEndOfLine : ~NEWLINE+ ;

/* Tokens
-------------------------------------------------- */

// Whitespace
NEWLINE : NEWLINE_CHAR+ ;
SPACE : SPACE_CHAR+ ;

// General
COMMENT_OPEN : '#' ;
BLOCK_NAME_OPEN : '@' ;
BLOCK_OPEN : '{' ;
BLOCK_CLOSE : '}' ;
GROUP_OPEN : '(' ;
GROUP_CLOSE : ')' ;
GROUP_ITEM_SEPARATOR : ',' ;
NAME_VALUE_SEPARATOR : '=' ;

// Tags
TAG_SET_SEPARATOR : [&|] ;

// Names and values
NAME : NAME_CHAR+ ;
PATH : PATH_CHAR+ ;

// Misc (eg. for comment text and context values)
OTHER : . ;

/* Character Classes
-------------------------------------------------- */

fragment NEWLINE_CHAR : ('\r'? '\n' | '\r') ;
fragment SPACE_CHAR : [\t ] ;

fragment NAME_CHAR : [A-Za-z0-9_-] ;
fragment PATH_CHAR : [A-Za-z0-9_/.-] ;
