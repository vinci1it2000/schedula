import React, {useEffect, useState} from "react";
import debounce from "lodash/debounce";
import './modal.css';

const Modal = React.lazy(() => import('demisto-react-modal-resizable-draggable'));

function getWindowSize() {
    const {innerWidth, innerHeight} = window;
    return {innerWidth, innerHeight};
}

export default function ReactModal(props) {
    const [windowSize, setWindowSize] = useState(getWindowSize());

    useEffect(() => {
        function handleWindowResize() {
            if (props.isOpen)
                setWindowSize(getWindowSize());
        }

        window.addEventListener('resize', debounce(handleWindowResize, 500));
    }, [props.isOpen]);
    return <Modal
        initHeight={windowSize.innerHeight * 0.6}
        initWidth={windowSize.innerWidth * 0.6}
        {...props}/>
}