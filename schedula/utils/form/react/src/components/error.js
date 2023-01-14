import React, {useState, Suspense} from "react";
import ErrorIcon from "@mui/icons-material/Error";
import CloseIcon from "@mui/icons-material/Close";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";

const Box = React.lazy(() => import('@mui/material/Box'));
const Badge = React.lazy(() => import('@mui/material/Badge'));
const Alert = React.lazy(() => import('@mui/material/Alert'));
const Stack = React.lazy(() => import('@mui/material/Stack'));
const AlertTitle = React.lazy(() => import('@mui/material/AlertTitle'));
const Fab = React.lazy(() => import('@mui/material/Fab'));


const ErrorList = ({errors}) => {
    const [open, setOpen] = useState(false);
    const setToggle = () => {
        setOpen(!open)
    };
    return (<Suspense>
        <Box
            sx={{position: 'fixed', top: 84, right: 16, "z-index": 1050}}
            key={'error'}
        >
            <div>{!open ? (
                    <Fab size="small" onClick={setToggle}>
                        <Badge color="error"
                               badgeContent={errors.length} max={99}>
                            <ErrorIcon/>
                        </Badge>
                    </Fab>) :
                (<Stack
                    direction="row"
                    justifyContent="flex-end"
                    alignItems="flex-start"
                    spacing={0}>
                    <Alert severity="error">
                        <AlertTitle>Errors</AlertTitle>
                        <List dense={true}
                              sx={{maxWidth: "50%", maxHeight: "30vh"}}>
                            {errors.map((error, i) => (
                                    <ListItem key={i}>{error.stack}</ListItem>
                                )
                            )}
                        </List>
                    </Alert>
                    <Fab size="small" onClick={setToggle}>
                        <CloseIcon/>
                    </Fab>
                </Stack>)}</div>
        </Box>
    </Suspense>);
};

export default ErrorList;