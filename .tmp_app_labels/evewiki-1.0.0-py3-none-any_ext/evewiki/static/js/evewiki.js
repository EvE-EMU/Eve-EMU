(function() {

	const Tree = class Tree {
        constructor(root_class, default_expand_selected=false) {

			var selected = document.querySelector('.'+root_class+' li.selected');
            var leaves = document.querySelectorAll('.'+root_class+' li');

            // Loop through the tree applying click event to show branches.
            for(var i=0; i < leaves.length; i++) {
                var leaf = leaves[i];
                var expand_icon = leaf.querySelector('span.expand-icon');
                // Not all branches can be expanded.
                if(expand_icon == null) {
                    continue;
                }
                expand_icon.addEventListener("click", function(evt) {
                    evt.preventDefault();
                    // A lead is the parent li of the expan-icon.
                    var leaf = this.parentNode.parentNode;
                    var immediate_children = leaf.querySelectorAll(':scope > ul');
                    for(var j=0; j < immediate_children.length; j++) {
                        var child = immediate_children[j];
                        if( child.style.display == 'block') {
                            child.style.display = 'none';
                            leaf.classList.remove("expanded");
                        } else {
                            child.style.display = 'block';
                            leaf.classList.add("expanded");
                        }
                    }
                });
            }

            if(selected !== null && default_expand_selected == true) {
                selected.classList.add("expanded");
                var immediate_children = selected.querySelectorAll(':scope > ul');
                for(var j=0; j < immediate_children.length; j++) {
                    var child = immediate_children[j];
                    if( child.style.display != 'block') {
                        child.style.display = 'block';
                    }
                }
            }

            // Loop back through the selected elements parent and set them to be displayed.
            this.loopParents(selected, function(el, i, child){
                if(el.classList.contains(root_class)) {
                    return true;
                }
                el.style.display = 'block';
                this.classList.add("expanded");
            })
        }

        /**
         * Apply the given function to all childs parents.
         * @param element el
         * @param function forParent
         * @return boolean
         */
        loopParents(el, forParent) {
            var node = el,i = 0;
            while (node != null) {
                node = node.parentNode;
                if(node){
                    if(forParent.call(node, node, i, el)){
                        return false;
                    }
                }
                i += 1;
            }
            return true;
        }
    }

	function setEditToolbar(mode) {

		if (document.getElementById('save_content') == null) {
			return;
		}

		save_content = document.getElementById('save_content');
		the_output = document.getElementById('the_output');

		btn_view = document.getElementById('mode_view');
		btn_edit = document.getElementById('mode_edit');
		btn_raw = document.getElementById('mode_raw');

		save_content.style.display = 'none';

		btn_view.classList.remove('btn-primary');
		btn_view.classList.remove('btn-secondary');

		btn_edit.classList.remove('btn-primary');
		btn_edit.classList.remove('btn-secondary');

		btn_raw.classList.remove('btn-primary');
		btn_raw.classList.remove('btn-secondary');

		if (mode == 'edit') {
			save_content.style.display = 'block';
			the_output.style.display = 'none';
			btn_view.classList.add('btn-secondary');
			btn_edit.classList.add('btn-primary');
			btn_raw.classList.add('btn-secondary');
		} else if (mode == 'raw') {
			save_content.style.display = 'block';
			the_output.style.display = 'none';
			btn_view.classList.add('btn-secondary');
			btn_edit.classList.add('btn-secondary');
			btn_raw.classList.add('btn-primary');
		} else {
			save_content.style.display = 'none';
			the_output.style.display = 'block';
			btn_view.classList.add('btn-primary');
			btn_edit.classList.add('btn-secondary');
			btn_raw.classList.add('btn-secondary');
		}
	}

	function setEasyMde(mode = 'view') {

		let options;
		switch(mode) {
			case 'view':
				options = {
					readOnly: true,
					toolbar: false,
					status: false
				};
				break;
			case 'edit':
				options = {
					sideBySideFullscreen: false,
					hideIcons: ['fullscreen'],
				};
				break;
			case 'raw':
				options = {
					lineNumbers: true,
					toolbar: false,
					sideBySideFullscreen: false,
					hideIcons: ['fullscreen'],
					previewRender: (plainText) => plainText
				};
				break;
		}

		// Reset
		if (window.easyMDE !== undefined) {
			window.easyMDE.toTextArea();
			window.easyMDE.cleanup();
			window.easyMDE = null;
		}

		var easyMDE = new EasyMDE({
			element: document.getElementById('id_content'),
			theme: 'bootstrap-dark',
			...options
		});

		if (mode == 'view') {
			// Ensure the input is disabled (in case someone tries to edit via JS)
			easyMDE.codemirror.getInputField().disabled = true;
			easyMDE.codemirror.getWrapperElement().closest('.EasyMDEContainer').style.display = 'none';

			// Get the content of the preview
			var output_pane = document.getElementById('the_output')
			var markdown = easyMDE.value();
			var previewHTML = easyMDE.options.previewRender(markdown);
			output_pane.innerHTML = previewHTML;
		}

		if (mode == 'raw') {
			easyMDE.codemirror.getWrapperElement().style.fontFamily = "'Fira Mono', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', monospace";
		}

		window.easyMDE = easyMDE;
		setEditToolbar(mode);
	}


	new Tree('tree', true)
	setEasyMde();

	if (document.querySelector('#mode_view') !== null) {
		document.querySelector('#mode_view')
		.addEventListener("click", function(evt) {
			setEasyMde();
		});
		document.querySelector('#mode_edit')
		.addEventListener("click", function(evt) {
			setEasyMde('edit');
		});
		document.querySelector('#mode_raw')
		.addEventListener("click", function(evt) {
			setEasyMde('raw');
		});
	}
})();
