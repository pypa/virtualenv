Keep non-ASCII csh activation values byte-exact across shell locale changes. ``tcsh`` could misread quotes after prompt
text in Big5-HKSCS or turn a destination character into a ``PATH`` separator after switching to the C locale. Generated
``.csh`` files with non-ASCII values may contain raw bytes rather than valid UTF-8.
