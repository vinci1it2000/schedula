import React from 'react';
import PropTypes from 'prop-types';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import Fade from '@mui/material/Fade';
import useScrollTrigger from '@mui/material/useScrollTrigger';
import Fab from '@mui/material/Fab';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';

function ScrollTop(props) {
    const {children, window} = props;
    // Note that you normally won't need to set the window ref as useScrollTrigger
    // will default to window.
    // This is only being set here because the demo is in an iframe.
    const trigger = useScrollTrigger({
        target: window ? window() : undefined,
        disableHysteresis: true,
        threshold: 100,
    });

    const handleClick = (event) => {
        const anchor = (event.target.ownerDocument || document).querySelector(
            '#back-to-top-anchor',
        );

        if (anchor) {
            anchor.scrollIntoView({
                block: 'center',
            });
        }
    };

    return (
        <Fade in={trigger}>
            <Box
                onClick={handleClick}
                role="presentation"
                sx={{position: 'fixed', bottom: 16, right: 16}}
            >
                {children}
            </Box>
        </Fade>
    );
}

ScrollTop.propTypes = {
    children: PropTypes.element.isRequired,
    /**
     * Injected by the documentation to work in an iframe.
     * You won't need it on your project.
     */
    window: PropTypes.func,
};

function a11yProps(index) {
    return {
        id: `tab-${index}`,
        'aria-controls': `tabpanel-${index}`,
    };
}

export default function _nav(props) {
    const [value, setValue] = React.useState(props.current_tab || 0);
    const handleChange = (event, newValue) => {
        setValue(newValue);
    };

    return (
        <React.Fragment>
            <AppBar color="inherit" {...props}>
                <Toolbar>
                    <Box key={0}>{props['children-left']}</Box>
                    <Tabs key={1}
                          value={value}
                          onChange={handleChange}
                          sx={{flexGrow: 1}}
                          {...props}
                    >
                        {props.children.map((element, index) => (
                            <Tab key={index}
                                 label={(element.props.schema || {}).title || ''} {...((props['tabs-props'] || {})[index] || {})}{...a11yProps(index)} />
                        ))}
                    </Tabs>
                    <Box key={2}>{props['children-right']}</Box>
                </Toolbar>
            </AppBar>
            <Toolbar id="back-to-top-anchor"/>
            {props.children.map((element, index) => (
                value === index ?
                    <Container key={index} disableGutters maxWidth="xl"
                               component="main"
                               sx={{mt: 2}}>
                        {element}
                    </Container> : null
            ))}

            <ScrollTop  {...props}>
                <Fab size="small" aria-label="scroll back to top">
                    <KeyboardArrowUpIcon/>
                </Fab>
            </ScrollTop>
        </React.Fragment>
    );
}