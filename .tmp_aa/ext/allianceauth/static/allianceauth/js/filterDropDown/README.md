# filterDropDown JavaScript Library

## How to generate the `.min.js` and `.map` files

To generate the minified JavaScript file and the source map, `Terser` is used. You can install it globally using npm:

```bash
npm install terser
```

Once you have `Terser` installed, navigate to the directory containing your JavaScript file and run the following command:

```bash
terser filterDropDown.js -o filterDropDown.min.js --source-map "url='filterDropDown.min.js.map'" --compress reduce_vars=false --mangle --format quote_style=1
```
